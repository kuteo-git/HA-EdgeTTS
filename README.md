# EdgeTTS for Home Assistant

A Home Assistant custom integration that provides high-quality text-to-speech using Microsoft's EdgeTTS service.

## Features

- 🗣️ High-quality text-to-speech using Microsoft EdgeTTS
- 🌍 Supports 400+ voices in 100+ languages
- 💨 Fast concurrent processing for long texts
- 💾 Smart caching system
- 🔧 Easy HACS installation
- 🎛️ Simple configuration via UI

## Installation via HACS (Recommended)

1. **Add Custom Repository**:
   - Open HACS in your Home Assistant
   - Go to "Integrations"
   - Click the three dots menu → "Custom repositories"
   - Add this repository URL: `https://github.com/kuteo/HA-EdgeTTS`
   - Select "Integration" as the category
   - Click "Add"

2. **Install the Integration**:
   - Search for "EdgeTTS" in HACS
   - Click "Download"
   - Restart Home Assistant

3. **Configure the Integration**:
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "EdgeTTS"
   - Follow the configuration steps

## Manual Installation

1. Download the `custom_components/edgetts` folder
2. Copy it to your `config/custom_components/` directory
3. Restart Home Assistant
4. Add the integration via the UI

## Usage

### Using the Service

Call the `edgetts.speak` service with your desired parameters:

```yaml
service: edgetts.speak
data:
  entity_id: media_player.your_speaker
  message: "Hello! This is EdgeTTS speaking."
  voice: "en-US-JennyNeural"
  cache: true
```

### In Automations

```yaml
automation:
  - trigger:
      platform: state
      entity_id: binary_sensor.front_door
      to: "on"
    action:
      - service: edgetts.speak
        data:
          entity_id: media_player.living_room_speaker
          message: "Front door opened!"
          voice: "en-US-JennyNeural"
```

### Service Parameters

- `entity_id` (required): Media player entity to play the audio
- `message` (required): Text to convert to speech
- `voice` (optional): Voice to use (defaults to Vietnamese)
- `cache` (optional): Enable/disable caching (default: true)

## Supported Voices

The integration supports 400+ voices from Microsoft EdgeTTS. Here are some popular ones:

### English
- `en-US-JennyNeural` - English (US) - Jenny
- `en-US-GuyNeural` - English (US) - Guy  
- `en-GB-LibbyNeural` - English (UK) - Libby

### Vietnamese
- `vi-VN-NamMinhNeural` - Vietnamese - Nam Minh
- `vi-VN-HoaiMyNeural` - Vietnamese - Hoai My

### Other Languages
- `zh-CN-XiaoxiaoNeural` - Chinese (Mandarin)
- `ja-JP-NanamiNeural` - Japanese
- `ko-KR-SunHiNeural` - Korean
- `fr-FR-DeniseNeural` - French
- `de-DE-KatjaNeural` - German
- `es-ES-ElviraNeural` - Spanish
- `it-IT-ElsaNeural` - Italian

For a complete list of available voices, visit the [Microsoft Edge TTS documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support#neural-voices).

## Configuration Options

- **Host**: EdgeTTS server host (default: 127.0.0.1)
- **Port**: EdgeTTS server port (default: 115)

## How It Works

1. **Server Management**: The integration automatically starts and manages an EdgeTTS server
2. **Text Processing**: Long texts are split into chunks for optimal processing
3. **Concurrent Generation**: Multiple audio chunks are generated simultaneously
4. **Audio Assembly**: Chunks are combined with appropriate silence gaps
5. **Caching**: Generated audio is cached to improve performance
6. **Media Playback**: Audio is served via Home Assistant's www folder

## Troubleshooting

### Integration Not Loading
- Check Home Assistant logs for errors
- Ensure all dependencies are installed
- Restart Home Assistant after installation

### TTS Not Playing
- Verify your media player entity is correct
- Check if the www/tts folder exists in your config directory
- Review EdgeTTS server logs

### Voice Not Found
- Use exact voice names from the supported list
- Check the [Microsoft Edge TTS documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support#neural-voices) for valid voices

## Migration from PyScript Version

If you're upgrading from the PyScript version:

1. Remove old PyScript files from `config/pyscript/`
2. Remove PyScript configuration from `configuration.yaml`
3. Install this integration via HACS
4. Update your automations to use `edgetts.speak` service

## Contributing

Contributions are welcome! Please feel free to submit pull requests or create issues for bugs and feature requests.

## License

This project is licensed under the MIT License.

## Acknowledgments

- Microsoft for providing the EdgeTTS service
- Home Assistant community for integration framework
- HACS for making custom integrations easy to install
