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

Windows CI compiles Python source, runs configuration smoke tests, and packages a standalone executable. These checks do not exercise microphone hardware or validate live backend credentials.

## Shared backend and limitations

- The desktop client uses the JARVIS backend endpoint and can be configured to use a compatible chat-completions endpoint. Use the **JARVIS client token** in the client; keep the OpenRouter secret only in the backend environment.
- Backend SQLite memory may not survive service restarts unless persistent storage is configured. The current backend memory API is a single shared collection per deployment, not per-user accounts.
- General AI responses require internet, a working backend client token, a valid server-side OpenRouter key, and an available upstream model. The free-model router can have rate limits or model capability differences.
- Windows wake-word listening requires a configured Picovoice AccessKey; typed chat does not. Speech transcription may require internet and microphone permissions.
- Test AI chat, memory, audio, and Windows actions on the target PC before relying on them.
- Never commit API keys or Picovoice AccessKeys.

## Development checks

- Windows desktop: Python compilation, configuration smoke tests, and executable packaging in GitHub Actions.
- Backend: run `python -m unittest discover -s tests -v` from `backend`.
