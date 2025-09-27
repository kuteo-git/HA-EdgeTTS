"""The EdgeTTS integration."""
from __future__ import annotations

import logging
import os
import hashlib
import re
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, TTS_CACHE_DIR
from .server_manager import EdgeTTSServerManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EdgeTTS from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Initialize server manager
    server_manager = EdgeTTSServerManager(hass)
    hass.data[DOMAIN][entry.entry_id] = {
        "server_manager": server_manager,
        "host": entry.data.get("host", DEFAULT_HOST),
        "port": entry.data.get("port", DEFAULT_PORT)
    }
    
    # Start the EdgeTTS server
    await server_manager.start_server()
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_speak_service(call: ServiceCall) -> None:
        """Handle the speak service call."""
        await _handle_speak_service(hass, entry.entry_id, call)
    
    hass.services.async_register(
        DOMAIN,
        "speak",
        handle_speak_service,
        schema=None
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Stop the server
        if entry.entry_id in hass.data[DOMAIN]:
            server_manager = hass.data[DOMAIN][entry.entry_id]["server_manager"]
            await server_manager.stop_server()
            hass.data[DOMAIN].pop(entry.entry_id)
            
        # Remove services
        hass.services.async_remove(DOMAIN, "speak")
    
    return unload_ok


def _clean_text_for_tts(text: str) -> str:
    """Clean text for TTS processing."""
    text = text.replace('"', "")
    text = text.replace("*", "")
    text = text.replace(":", ",")
    text = re.sub(r'\s*\n\s*', '. ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def _handle_speak_service(hass: HomeAssistant, entry_id: str, call: ServiceCall) -> None:
    """Handle speak service call."""
    try:
        entity_id = call.data.get("entity_id")
        message = call.data.get("message", "")
        voice = call.data.get("voice", "vi-VN-NamMinhNeural")
        cache = call.data.get("cache", True)
        
        if not entity_id or not message:
            _LOGGER.error("entity_id and message are required")
            return
            
        # Get configuration
        config_data = hass.data[DOMAIN][entry_id]
        host = config_data["host"]
        port = config_data["port"]
        
        # Ensure cache directory exists
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        
        # Clean the message text
        message = _clean_text_for_tts(message)
        
        # Generate hash for caching
        md5_hash = hashlib.md5(message.encode()).hexdigest()
        file_name = f'{md5_hash}.mp3'
        
        if not cache:
            file_name = 'edgetts_no_cache.mp3'
            
        tts_file_path = f'{TTS_CACHE_DIR}/{file_name}'
        
        # Check if file already exists to avoid regenerating
        should_gen_tts = not os.path.exists(tts_file_path)
        
        if not cache:
            should_gen_tts = True
            try:
                if os.path.exists(tts_file_path):
                    os.remove(tts_file_path)
                    _LOGGER.info(f"TTS file removed (cache=False): {tts_file_path}")
            except Exception as cleanup_error:
                _LOGGER.warning(f"Could not remove TTS file: {cleanup_error}")
        
        if should_gen_tts:
            _LOGGER.info(f"Generating TTS for: {file_name}")
            
            # Send request to EdgeTTS server
            headers = {"Content-Type": "application/json"}
            data = {
                "text": message,
                "voice": voice,
                "silence_duration": 150
            }
            
            url = f'http://{host}:{port}/tts'
            
            def make_request():
                return requests.post(url, headers=headers, json=data, timeout=30)
                
            response = await hass.async_add_executor_job(make_request)
            
            if response.status_code == 200:
                # Save the audio data
                with open(tts_file_path, "wb") as f:
                    f.write(response.content)
                _LOGGER.info(f"TTS generation complete: {file_name}")
            else:
                _LOGGER.error(f"EdgeTTS server error {response.status_code}: {response.text}")
                return
        
        # Use the correct media content ID format for www folder
        media_content_id = f'/local/tts/{file_name}'
        
        _LOGGER.info(f"Playing TTS audio on {entity_id}")
        
        # Play the media
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
        
        _LOGGER.info("TTS playback initiated successfully")
        
    except Exception as err:
        _LOGGER.error(f"Error in speak service: {str(err)}")
