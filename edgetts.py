import re
import os
import hashlib
import asyncio
import requests
from file_manager import write_file

__TTS_BASE_URL = 'http://127.0.0.1:115'
__FOLDER_PATH = '/config/www/tts'


def clean_text_for_tts(text: str) -> str:
    text = text.replace("\"", "")
    text = text.replace("*", "")
    text = text.replace(":", ",")
    text = re.sub(r'\s*\n\s*', '. ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def send_text_to_tts_server(
    text: str,
    speed: float = 0.95,
    sentence_pause: float = 2.0,
    comma_pause: float = 0.3,
):
    text = clean_text_for_tts(text)
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "speed": speed,
        "sentence_pause": sentence_pause,
        "comma_pause": comma_pause
    }

    try:
        response = task.executor(requests.post, f'{__TTS_BASE_URL}:8000/luke_tts', headers=headers, json=data, timeout=1000000000)
        if response.status_code == 200:
            return response.content
        else:
            log.error(f"❌ [edge_tts] Failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log.error(f"❌ [edge_tts] Exception occurred: {e}")
        return None

def send_text_to_edge_tts_server(
    text: str,
    voice: str,
    silence_duration: int = 150
):
    text = clean_text_for_tts(text)
    # log.error(f"text === {text}")
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voice": voice,
        "silence_duration": silence_duration
    }

    try:
        response = task.executor(requests.post, f'{__TTS_BASE_URL}/tts', headers=headers, json=data, timeout=1000000000)
        if response.status_code == 200:
            return response.content
        else:
            log.error(f"❌ [edge_tts] Failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log.error(f"❌ [edge_tts] Exception occurred: {e}")
        return None


@service
async def speech(
    text: str,
    entity_id: str,
    voice: str = "vi-VN-NamMinhNeural",
    cache: bool = True
):
    try:
        # Ensure the directory exists
        os.makedirs(__FOLDER_PATH, exist_ok=True)
        
        # Generate hash for caching
        md5_hash = hashlib.md5(text.encode()).hexdigest()

        file_name = f'{md5_hash}.mp3'
        if cache == False:
            file_name = 'luke_no_cache_tts.mp3'

        tts_file_path = f'{__FOLDER_PATH}/{file_name}'
        
        # Check if file already exists to avoid regenerating
        should_gen_tts = not os.path.exists(tts_file_path)

        if cache == False:
            should_gen_tts = True
            try:
                await os.remove(tts_file_path)
                log.info(f"[edge_tts] ##### TTS file removed (cache=False, fallback): {tts_file_path}")
            except Exception as cleanup_error:
                log.warning(f"[edge_tts] ##### Could not remove TTS file in fallback: {cleanup_error}")
            

        if should_gen_tts:
            log.info(f"[edge_tts] ##### Gen tts .... {file_name}")

            data = send_text_to_edge_tts_server(
                text = text,
                voice = voice
            )

            write_file(data, tts_file_path)

            log.info(f"[edge_tts] ##### Gen tts .... {file_name} -- DONE")
        
        # Use the correct media content ID format for www folder
        media_content_id = f'/local/tts/{file_name}'

        log.info(f"[edge_tts] ##### Try to play the media...")

        # Try to play the media
        await hass.services.async_call(
            "media_player", 
            "play_media",
            {
                "entity_id": entity_id,
                "media_content_id": media_content_id,
                "media_content_type": "audio/mpeg",
                "announce": True
            }
        )
        log.info(f"[edge_tts] ##### Task -- DONE")
    except Exception as e:
        log.error(f"[edge_tts] ##### Error in edge_tts_speech: {str(e)}")


@service
async def test_speech():
    speech(
        text = "Xin chào các bạn! Đây là tiếng Việt!",
        entity_id = "media_player.family_room_speaker",
        voice = "vi-VN-NamMinhNeural", # vi-VN-HoaiMyNeural, vi-VN-NamMinhNeural, ...
        cache = False
    )