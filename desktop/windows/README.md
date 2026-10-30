# JARVIS Desktop for Windows 11

This repository currently contains the native Windows laptop edition of JARVIS. The Android edition is maintained separately. It provides a blue JARVIS-themed command dashboard, separate conversation window, text input, spoken replies, persistent local chat history, a small allowlist of safe Windows app/website commands, and optional always-listening wake-word detection through Picovoice Porcupine.

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

Press **Save settings**. To test without a Picovoice key, type a message and press **Send**; wake listening requires a separate Picovoice AccessKey. The main window shows the blue holographic command dashboard with an animated reactor, resource panel, quick-access folders, and voice/chat controls. Use CHAT LOG to open the conversation transcript and SETTINGS to configure the backend, wake-word key, and optional Windows sign-in startup. Closing the main window moves JARVIS to the Windows system tray; use the tray menu to reopen it, activate/stop voice listening, or fully exit. The startup option adds/removes a per-user Windows Run registry entry and does not require administrator access. Conversations are saved in `%APPDATA%\\JARVISDesktop\\chat_history.json`; Clear conversation also clears that saved history. Exact commands currently supported include `open notepad`, `open calculator`, `open downloads`, `open downloads folder`, `open file explorer`, `open task manager`, `open browser`, `open google`, `open youtube`, `volume up`, `volume down`, `mute`, `play pause`, `next track`, and `previous track`, `brightness up`, and `brightness down`. Media/volume actions use fixed Windows multimedia key events; brightness changes use 10-point steps on the primary supported display; arbitrary shell commands are not executed. The dashboard POWER control opens a confirmation dialog for shutdown/restart; both are scheduled 60 seconds ahead and can be cancelled from the same dialog. These actions are never triggered by an unconfirmed chat phrase. Say “Jarvis”, wait for the listening status, then speak a command. After wake detection, the microphone checks for a command in cancellable one-second start-of-phrase intervals; stopping during an already-started phrase may still wait until the current phrase capture ends (up to the configured 12-second phrase limit). You can also send a typed message without enabling the microphone.

Keys are stored using the Windows Credential Manager through Python's `keyring` package. The endpoint and model are stored in the current user's AppData folder. Do not put keys in source files, screenshots, or Git commits.

## Build a Windows executable

From the same folder, after installing requirements:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name JARVIS jarvis_desktop.py
```

The executable is written to `dist\JARVIS.exe`. Keep the original `requirements.txt` and this guide for maintenance. Some endpoint/microphone/Picovoice configurations can require troubleshooting on the target PC.

## Current scope and limitations

- This Windows edition has its own UI, settings, voice loop, and local chat history. It does not sync its history or settings with the separate Android edition.
- Speech-to-text is online and the Settings language selector supports English (India) (also suitable for many Hinglish phrases), Hindi (India), and English (US). AI replies can be in Hindi, English, or Hinglish based on the prompt. Use STOP SPEECH on the dashboard or Stop speaking in the tray menu to interrupt spoken replies.
- Test the microphone and wake word on the actual Windows laptop before relying on continuous listening.


## Automated installer artifact

The Windows CI builds both a portable `JARVIS.exe` and an Inno Setup installer named `JARVIS-Setup-x64.exe`. After a successful `Windows Desktop Checks` workflow, download the `JARVIS-Windows-Installer-x64` artifact from the run's Artifacts section. The installer creates a Start Menu shortcut and offers an optional Desktop shortcut. It installs per-user without administrator privileges; automatic startup is opt-in from SETTINGS and can be disabled there.
