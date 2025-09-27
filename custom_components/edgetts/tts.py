"""Support for EdgeTTS text-to-speech service."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import requests
from typing import Any

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, TTS_CACHE_DIR

_LOGGER = logging.getLogger(__name__)

# Supported voices (subset for example - add more as needed)
SUPPORTED_VOICES = {
    "en-US-JennyNeural": "English (US) - Jenny",
    "en-US-GuyNeural": "English (US) - Guy",
    "en-GB-LibbyNeural": "English (UK) - Libby",
    "vi-VN-NamMinhNeural": "Vietnamese - Nam Minh",
    "vi-VN-HoaiMyNeural": "Vietnamese - Hoai My",
    "zh-CN-XiaoxiaoNeural": "Chinese (Mandarin) - Xiaoxiao",
    "ja-JP-NanamiNeural": "Japanese - Nanami",
    "ko-KR-SunHiNeural": "Korean - Sun Hi",
    "fr-FR-DeniseNeural": "French - Denise",
    "de-DE-KatjaNeural": "German - Katja",
    "es-ES-ElviraNeural": "Spanish (Spain) - Elvira",
    "it-IT-ElsaNeural": "Italian - Elsa",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeTTS TTS platform."""
    host = config_entry.data.get("host", DEFAULT_HOST)
    port = config_entry.data.get("port", DEFAULT_PORT)
    
    async_add_entities([EdgeTTSProvider(hass, host, port)])


class EdgeTTSProvider(TextToSpeechEntity):
    """EdgeTTS speech provider."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize EdgeTTS provider."""
        self.hass = hass
        self._host = host
        self._port = port
        self._attr_name = "EdgeTTS"
        self._attr_unique_id = f"{DOMAIN}_tts"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "vi-VN-NamMinhNeural"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return list(SUPPORTED_VOICES.keys())

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options."""
        return ["voice", "cache"]

    def clean_text_for_tts(self, text: str) -> str:
        """Clean text for TTS processing."""
        text = text.replace('"', "")
        text = text.replace("*", "")
        text = text.replace(":", ",")
        text = re.sub(r'\s*\n\s*', '. ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> TtsAudioType:
        """Load TTS from EdgeTTS server."""
        if options is None:
            options = {}

        voice = options.get("voice", language)
        cache = options.get("cache", True)
        
        # Clean the message text
        message = self.clean_text_for_tts(message)
        
        try:
            # Ensure cache directory exists
            os.makedirs(TTS_CACHE_DIR, exist_ok=True)
            
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
                
                url = f'http://{self._host}:{self._port}/tts'
                response = await self.hass.async_add_executor_job(
                    requests.post, url, headers, data, 30  # 30 second timeout
                )
                
                if response.status_code == 200:
                    # Save the audio data
                    with open(tts_file_path, "wb") as f:
                        f.write(response.content)
                    _LOGGER.info(f"TTS generation complete: {file_name}")
                else:
                    _LOGGER.error(f"EdgeTTS server error {response.status_code}: {response.text}")
                    return None, None
            
            # Read the audio file
            with open(tts_file_path, "rb") as f:
                audio_data = f.read()
                
            return "mp3", audio_data
            
        except Exception as err:
            _LOGGER.error(f"Error in EdgeTTS: {str(err)}")
            return None, None

    def get_supported_voices_for_language(self, language: str) -> list[str]:
        """Get supported voices for a language."""
        # Return voices that start with the language code
        lang_code = language.split('-')[0] if '-' in language else language
        return [voice for voice in SUPPORTED_VOICES.keys() if voice.startswith(lang_code)]
