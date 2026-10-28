# JARVIS — Android and Windows desktop assistant

JARVIS is a personal AI assistant project with an Android app and an early native Windows desktop companion.

## Platforms

### Android
The Android app is built with Kotlin and Jetpack Compose. It includes voice interaction, AI-provider configuration, an agent/runtime layer, context and memory helpers, accessibility integrations, and Android-specific device features.

**Build and test:** Open the project in Android Studio, sync Gradle, and run the app on an Android device. See [offline wake-word setup](docs/OFFLINE_WAKE_WORD.md) for Picovoice configuration. The Android wake-word change is under review and still needs a real-device build/test before release.

### Windows 10/11 desktop
A separate Python/Tkinter companion is available in [desktop/windows](desktop/windows/README.md). It includes a JARVIS-themed chat UI, typed prompts, spoken AI replies, configurable OpenAI-compatible endpoint/model, and optional Picovoice wake-word listening.

Quick start in PowerShell:

```powershell
cd desktop\windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python jarvis_desktop.py
```

See the desktop guide for credential setup, packaging into a Windows executable, and current limitations.

## Shared behavior and current limitations

- Both apps can be configured to use a compatible chat-completions endpoint, but settings and conversation history do not sync automatically yet.
- Windows-specific UI/system actions and Android-specific accessibility/device actions are separate platform integrations; features are not automatically identical.
- Android local command support depends on the feature and device. General AI answers require a configured provider and internet.
- The Windows wake-word detector uses Porcupine, while command transcription currently uses Google's online speech recognition. It therefore does not provide fully offline voice transcription.
- API keys and Picovoice AccessKeys must be configured locally and must never be committed to the repository.
- Android and Windows build checks are not substitutes for testing microphones, wake-word detection, TTS, permissions, and app behavior on the actual devices.

## Development checks

- Android: use Android Studio/Gradle and run unit tests.
- Windows desktop: GitHub Actions compiles the Python source and runs configuration smoke tests on Windows.
