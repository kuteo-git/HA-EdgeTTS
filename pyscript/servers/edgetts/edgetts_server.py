import os
import hashlib
import edge_tts
import re
from pydub import AudioSegment
from flask import Flask, request, jsonify, send_file
import asyncio
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# Flask app setup
app = Flask(__name__)

# Configuration
folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')
HOST = '0.0.0.0'  # Allow external access
PORT = 115

# Global variable to track chunk generation
chunk_status = {}  # {index: {'generated': bool, 'file_path': str}}


def log_info(message):
    """Simple logging function"""
    # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # print(f"[{timestamp}] INFO: {message}")


def log_error(message):
    """Simple error logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ERROR: {message}")


def split_string_by_sentence(text, max_length=250):
    """Split text into chunks by grouping sentences up to max_length"""
    chunks = []
    current_chunk = ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        current_chunk += sentence + " "
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "edge-tts-api"})


@app.route('/tts', methods=['POST'])
def text_to_speech():
    """Convert text to speech and return MP3 file directly"""
    global chunk_status
    
    try:
        # Get JSON data from request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract parameters
        text = data.get('text', '')
        voice = data.get('voice', 'vi-VN-NamMinhNeural')
        silence_duration = data.get('silence_duration', 500)
        max_workers = data.get('max_workers', 4)  # Concurrent threads
        
        # Validate input
        if not text or not text.strip():
            return jsonify({
                "error": "Text parameter is required and cannot be empty"
            }), 400
        
        # Validate max_workers
        if (not isinstance(max_workers, int) or max_workers < 1 or 
                max_workers > 10):
            max_workers = 4  # Default to 4 if invalid
        
        log_info(f"Processing TTS request: {len(text)} characters, "
                 f"voice: {voice}, threads: {max_workers}")
        
        # Process the text to speech with concurrent processing
        result = process_sentences_sync(text, voice, silence_duration, 
                                        max_workers)
        
        if result['success']:
            # Return the MP3 file directly
            final_file_path = result['file_path']
            
            try:
                # Send file and then clean up
                response = send_file(
                    final_file_path,
                    mimetype='audio/mpeg',
                    as_attachment=True,
                    download_name='tts_output.mp3'
                )
                
                # Schedule cleanup using threading to avoid blocking
                def delayed_cleanup():
                    import time
                    time.sleep(1)  # Wait a bit for file to be sent
                    try:
                        if os.path.exists(final_file_path):
                            os.remove(final_file_path)
                            log_info(f"Cleaned up final file: "
                                     f"{final_file_path}")
                    except Exception as e:
                        log_error(f"Error cleaning up file: {str(e)}")
                
                cleanup_thread = threading.Thread(target=delayed_cleanup)
                cleanup_thread.daemon = True
                cleanup_thread.start()
                
                return response
                
            except Exception as e:
                # Clean up on error
                try:
                    if os.path.exists(final_file_path):
                        os.remove(final_file_path)
                except Exception:
                    pass
                raise e
        else:
            return jsonify({
                "success": False,
                "error": result['error']
            }), 500
            
    except Exception as e:
        log_error(f"Error in text_to_speech endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Get the current status of chunk generation"""
    global chunk_status
    total_chunks = len(chunk_status)
    generated_count = 0
    for s in chunk_status.values():
        if s['generated']:
            generated_count += 1
    
    return jsonify({
        'total_chunks': total_chunks,
        'generated_count': generated_count,
        'chunk_status': chunk_status
    })


def process_sentences_sync(text, voice, silence_duration, max_workers=8):
    """Process chunks concurrently without caching"""
    global chunk_status
    
    try:
        os.makedirs(folder_path, exist_ok=True)
        chunk_status.clear()

        # Split text into chunks using the new function
        chunks = split_string_by_sentence(text)
        total_chunks = len(chunks)
        log_info(f"Split into {total_chunks} chunks")

        # Create unique output filename (no cache check)
        timestamp = datetime.now().isoformat()
        text_hash = hashlib.md5(
            f"{text}_{voice}_{silence_duration}_{timestamp}".encode()
        ).hexdigest()
        final_file_name = f'tts_{text_hash}.mp3'
        final_file_path = f'{folder_path}/{final_file_name}'

        # Initialize status
        for i in range(total_chunks):
            chunk_status[i] = {'generated': False, 'file_path': ''}

        # Process chunks concurrently
        log_info(f"Starting concurrent processing with {max_workers} threads")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk processing tasks
            future_to_index = {
                executor.submit(generate_chunk_tts_sync, i, chunk, voice): i 
                for i, chunk in enumerate(chunks)
            }
            
            # Wait for all tasks to complete
            for future in as_completed(future_to_index):
                chunk_index = future_to_index[future]
                try:
                    future.result()  # Raise any exception that occurred
                    log_info(f"Chunk {chunk_index + 1} completed successfully")
                except Exception as e:
                    log_error(f"Chunk {chunk_index + 1} failed: {str(e)}")

        # Join audio files
        audio_duration = join_audio_files_sync(
            total_chunks, final_file_path, silence_duration
        )
        cleanup_chunk_files_sync(total_chunks)
        
        return {
            'success': True,
            'file_path': final_file_path,
            'audio_duration': audio_duration,
            'chunks_processed': total_chunks
        }

    except Exception as e:
        log_error(f"Error in process_sentences: {str(e)}")
        return {'success': False, 'error': str(e)}


def generate_chunk_tts_sync(chunk_index, chunk_text, voice):
    """Generate TTS for a single chunk (no caching)"""
    global chunk_status

    try:
        # Ensure chunk ends with proper punctuation
        if not chunk_text.rstrip().endswith(('.', '!', '?')):
            chunk_text += '.'

        log_info(f"[TASK {chunk_index+1}] Starting TTS generation...")

        # Create unique filename for each chunk
        timestamp = datetime.now().isoformat()
        chunk_hash = hashlib.md5(
            f"{chunk_text}_{voice}_{timestamp}".encode()
        ).hexdigest()
        file_name = f'chunk_{chunk_index+1}_{chunk_hash}.mp3'
        tts_file_path = f'{folder_path}/{file_name}'
        chunk_status[chunk_index]['file_path'] = tts_file_path

        # Always generate (no cache check)
        try:
            # Run async edge-tts in a thread
            def run_async_tts():
                async def async_tts():
                    communicate = edge_tts.Communicate(chunk_text, voice)
                    await communicate.save(tts_file_path)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(async_tts())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_async_tts)
            thread.start()
            thread.join(timeout=30)  # Wait max 30 seconds
            
            log_info(f"[TASK {chunk_index+1}] edge_tts completed")
        except Exception as e:
            log_error(f"[TASK {chunk_index+1}] TTS error: {str(e)}")

        # Check if file was created successfully
        try:
            if (os.path.exists(tts_file_path) and
                    os.path.getsize(tts_file_path) > 0):
                chunk_status[chunk_index]['generated'] = True
                file_size = os.path.getsize(tts_file_path)
                log_info(f"[TASK {chunk_index+1}] SUCCESS - "
                         f"File size: {file_size} bytes")
            else:
                chunk_status[chunk_index]['generated'] = False
                log_error(f"[TASK {chunk_index+1}] FAILED - "
                          f"File missing or empty")
        except Exception as e:
            chunk_status[chunk_index]['generated'] = False
            log_error(f"[TASK {chunk_index+1}] ERROR checking file: "
                      f"{str(e)}")

    except Exception as e:
        log_error(f"[TASK {chunk_index+1}] ERROR: {str(e)}")


def join_audio_files_sync(total_chunks, final_file_path, silence_duration):
    """Join all audio files with silence between them"""
    global chunk_status

    # Check if we have any generated files
    generated_count = 0
    for s in chunk_status.values():
        if s['generated']:
            generated_count += 1
    
    if generated_count == 0:
        log_error("No chunks generated successfully")
        raise Exception("No chunks generated successfully")

    log_info("Joining audio files...")
    
    silence = AudioSegment.silent(duration=silence_duration)
    combined_audio = AudioSegment.empty()

    for i in range(total_chunks):
        if i in chunk_status and chunk_status[i]['generated']:
            file_path = chunk_status[i]['file_path']
            if os.path.exists(file_path):
                audio_segment = AudioSegment.from_mp3(file_path)
                combined_audio += audio_segment
                if i < total_chunks - 1:
                    combined_audio += silence

    if len(combined_audio) > 0:
        combined_audio.export(final_file_path, format="mp3")
        audio_duration = len(combined_audio) / 1000.0  # Convert to seconds
        log_info(f"Final file created: {final_file_path} "
                 f"({audio_duration:.1f}s)")
        return audio_duration
    else:
        log_error("No audio to combine")
        raise Exception("No audio to combine")


def cleanup_chunk_files_sync(total_chunks):
    """Clean up individual chunk files after joining"""
    global chunk_status
    cleaned = 0
    for i in range(total_chunks):
        if i in chunk_status:
            file_path = chunk_status[i]['file_path']
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned += 1
                except Exception:
                    pass
    log_info(f"Removed {cleaned} chunk files")


if __name__ == '__main__':
    log_info(f"Starting Edge-TTS API server on {HOST}:{PORT}")
    log_info(f"Audio files will be saved to: {folder_path}")
    
    # Create audio directory if it doesn't exist
    os.makedirs(folder_path, exist_ok=True)
    
    # Start Flask app
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
