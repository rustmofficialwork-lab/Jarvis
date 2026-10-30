# JARVIS Desktop for Windows 11

This is the first native Windows companion for the existing Android JARVIS project. It is a separate desktop app, not an Android APK conversion. It provides a blue JARVIS-themed command dashboard, separate conversation window, text input, spoken replies, persistent local chat history, a small allowlist of safe Windows app/website commands, and optional always-listening wake-word detection through Picovoice Porcupine.

## Requirements

- Windows 10/11, 64-bit
- Python 3.11 (recommended)
- Microphone and speakers/headphones
- Internet for Google speech-to-text and online AI responses
- A Picovoice AccessKey for the Porcupine wake-word engine
- An OpenAI-compatible chat-completions endpoint and API key for AI replies

Wake-word inference runs locally after Porcupine initializes, but Picovoice may need internet to validate the AccessKey. Speech transcription currently uses Google's online recognizer; it is not offline speech-to-text. The desktop app does not hide or bypass Windows microphone privacy indicators.

## Run from source

Open PowerShell in this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python jarvis_desktop.py
```

In the app, enter:
- **Picovoice AccessKey** — from https://console.picovoice.ai/
- **AI endpoint** — default: `https://jarvis-backend-zqlw.onrender.com/v1/chat/completions`
- **Model** — default: `openrouter/free`
- **AI API key** — paste your JARVIS backend client token here (not your OpenRouter secret key). The OpenRouter key stays on the backend.

Press **Save settings**. To test without a Picovoice key, type a message and press **Send**; wake listening requires a separate Picovoice AccessKey. The main window shows the blue holographic command dashboard with an animated reactor, resource panel, quick-access folders, and voice/chat controls. Use CHAT LOG to open the conversation transcript and SETTINGS to configure the backend and wake-word key. Conversations are saved in `%APPDATA%\\JARVISDesktop\\chat_history.json`; Clear conversation also clears that saved history. Exact commands currently supported include `open notepad`, `open calculator`, `open file explorer`, `open task manager`, `open browser`, `open google`, `open youtube`, `volume up`, `volume down`, `mute`, `play pause`, `pause music`, `resume music`, `next track`, and `previous track`. Media/volume actions use fixed Windows multimedia key events; arbitrary shell commands are not executed. Say “Jarvis”, wait for the listening status, then speak a command. You can also send a typed message without enabling the microphone.

Keys are stored using the Windows Credential Manager through Python's `keyring` package. The endpoint and model are stored in the current user's AppData folder. Do not put keys in source files, screenshots, or Git commits.

## Build a Windows executable

From the same folder, after installing requirements:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name JARVIS jarvis_desktop.py
```

The executable is written to `dist\JARVIS.exe`. Keep the original `requirements.txt` and this guide for maintenance. Some endpoint/microphone/Picovoice configurations can require troubleshooting on the target PC.

## Current scope and limitations

- This desktop companion has its own UI and voice loop; it does not yet sync conversation history or settings automatically with Android.
- It shares the configurable OpenAI-compatible endpoint/model approach, but Android-only controls (accessibility, notifications, phone settings, etc.) are not available on Windows.
- Speech-to-text is online and currently defaults to English (India). AI replies can be in Hindi, English, or Hinglish based on the prompt.
- Test the microphone and wake word on the actual Windows laptop before relying on continuous listening.
