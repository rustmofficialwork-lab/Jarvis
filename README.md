# JARVIS — Windows desktop assistant

JARVIS is a Windows 10/11 desktop AI assistant with a dedicated Python/Tkinter application and a shared AI gateway backend.

## Windows desktop

The Windows application lives in [desktop/windows](desktop/windows/README.md). It is the only client platform maintained in this repository.

Quick start in PowerShell:

```powershell
cd desktop\windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python jarvis_desktop.py
```

Windows CI compiles Python source, runs the desktop unit tests, packages the portable `desktop/windows/dist/JARVIS/` application folder, builds the Inno Setup installer, uploads both artifacts, and publishes the rolling `jarvis-latest` prerelease on successful pushes to `main`. These checks do not exercise microphone hardware or validate live backend credentials.

## Wake word and voice

- Wake-word detection uses the local openWakeWord runtime. JARVIS prefers the custom-trained model at `%APPDATA%\\JARVISDesktop\\wakewords\\jarvis_first_party.onnx` when installed; otherwise it falls back to the separately licensed community Jarvis model.
- A custom first-party classifier must be trained using [WAKEWORD_FIRST_PARTY_MODEL.md](desktop/windows/WAKEWORD_FIRST_PARTY_MODEL.md) and imported with `py install_first_party_wakeword.py --model PATH --confirm`. No trained first-party model binary is checked into this repository yet.
- The voice setup wizard supports explicit local owner voice enrollment. The derived ECAPA profile is kept in Windows Credential Manager and checked after wake-word detection, before command capture. See [OWNER_VOICE_SETUP.md](desktop/windows/OWNER_VOICE_SETUP.md).
- The speaker model is downloaded only during the explicit enrollment action; subsequent verification runs locally through ONNX Runtime. Voice matching is not liveness detection or strong authentication.
- Speech transcription uses the configured online recognizer with the project's optional local Vosk fallback. Wake-word detection, owner verification, and speech transcription are separate stages.
- To list microphones and test a specific Windows input device, see [JARVIS_WAKEWORD_SETUP.md](desktop/windows/JARVIS_WAKEWORD_SETUP.md). Hardware behavior must be tested on the target PC; CI cannot verify a real microphone.

## Shared backend and limitations

- New desktop installs automatically enroll with the JARVIS backend and receive a unique, short-lived device credential. Existing manually provisioned client tokens remain supported for migration; keep the OpenRouter secret only in the backend environment.
- Personal memories are stored locally on each Windows installation; the backend does not expose a memory API or persist chat history.
- General AI responses require internet, a working backend client token, a valid server-side OpenRouter key, and an available upstream model. The free-model router can have rate limits or model capability differences.
- Test AI chat, memory, audio, and Windows actions on the target PC before relying on them.
- Never commit API keys or access tokens.

## Development checks

- Windows desktop: Python compilation, configuration smoke tests, and executable packaging in GitHub Actions.
- Backend: run `python -m unittest discover -s tests -v` from `backend`.
