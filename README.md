# JARVIS — Android and Windows desktop assistant

JARVIS is a personal assistant project with an Android app, a separate Windows desktop companion, and a shared AI gateway backend.

## Platforms

### Android
The Android app uses Kotlin and Jetpack Compose. It includes voice interaction, AI-provider configuration, agent/runtime helpers, context and memory components, accessibility integrations, image text extraction, and Android device actions.

**Build/test:** Android CI builds the debug APK and runs JVM unit tests. These checks do not replace real-device testing for microphone/wake-word behavior, speech recognition, text-to-speech, permissions, camera/torch, phone actions, or accessibility features. See [offline wake-word setup](docs/OFFLINE_WAKE_WORD.md) for configuration details.

### Windows 10/11 desktop
The separate Python/Tkinter companion in [desktop/windows](desktop/windows/README.md) includes typed chat, spoken AI replies, an animated orange orb, configurable endpoint/model, and optional Picovoice wake-word listening.

Quick start in PowerShell:

```powershell
cd desktop\windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python jarvis_desktop.py
```

Windows CI compiles Python source, runs configuration smoke tests, and packages a standalone executable. It does not exercise microphone hardware or validate real backend credentials.

## Shared backend and limitations

- Both clients default to the JARVIS backend endpoint and can be configured to use a compatible chat-completions endpoint. Use the **JARVIS client token** in the client; keep the OpenRouter secret only in the backend environment.
- Settings and conversation history do not automatically sync between Android and Windows.
- Windows system actions and Android device/accessibility actions are separate platform integrations; features are not identical across platforms.
- Android speech recognition and Windows speech transcription may require internet and permissions. Windows wake-word listening requires a configured Picovoice AccessKey; typed chat does not.
- General AI responses require internet, a working backend client token, a valid server-side OpenRouter key, and an available upstream model. The free-model router can have rate limits or model capability differences.
- Backend SQLite memory may not survive service restarts unless persistent storage is configured. The current backend memory API is a single shared collection per deployment, not per-user accounts.
- Build/unit tests are not proof that every live integration works on a real device. Test AI chat, memory, audio, permissions, and platform actions before relying on them.
- Never commit API keys or Picovoice AccessKeys.

## Development checks

- Android: Gradle debug build and JVM unit tests in GitHub Actions.
- Windows desktop: Python compilation, configuration smoke tests, and executable packaging in GitHub Actions.
- Backend: run `python -m unittest discover -s tests -v` from `backend`.
