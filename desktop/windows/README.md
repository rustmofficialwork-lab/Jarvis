# JARVIS Desktop for Windows 11

This repository currently contains the native Windows laptop edition of JARVIS. The Android edition is maintained separately. It provides a blue JARVIS-themed command dashboard, separate conversation window, text input, spoken replies, persistent local chat history, offline-first private personal memory, a small allowlist of safe Windows app/website commands, and optional always-listening wake-word detection through Picovoice Porcupine.

## Requirements

- Windows 10/11, 64-bit
- Python 3.11 (recommended)
- Microphone and speakers/headphones
- Internet for online AI responses and the one-time download of offline speech models
- A Picovoice AccessKey for the Porcupine wake-word engine
- An OpenAI-compatible chat-completions endpoint and API key for AI replies

Wake-word inference runs locally after Porcupine initializes, but Picovoice may need internet to validate the AccessKey. Speech transcription tries Google's online recognizer first and automatically falls back to a local Vosk model when the network request fails. JARVIS automatically downloads the selected language model in the background on first launch (and after a language change) when internet is available; no Settings visit is required. After the one-time download, speech transcription and allowlisted Windows commands can work without internet. Online recognition requests have an eight-second network timeout. Offline models are stored under `%LOCALAPPDATA%\\JARVISDesktop\\models` and are not bundled into the installer. The desktop app does not hide or bypass Windows microphone privacy indicators.

## Offline reminders

JARVIS can create local reminders by typing or speaking commands such as:

- `remind me in 10 minutes to drink water`
- `remind me at 18:30 to call home`
- `mujhe 2 ghante baad meeting yaad dilana`
- `show reminders`
- `delete reminder 3`

Reminders are stored in `%LOCALAPPDATA%\\JARVISDesktop\\reminders.sqlite3` and work without internet. On Windows, JARVIS registers a one-shot, current-user Task Scheduler task for each reminder. A small notification-only JARVIS process displays a native Windows reminder dialog even when the main app is closed. The user must still be signed in and the PC must be awake; reminders cannot wake a powered-off PC, and delivery after sleep depends on Windows Task Scheduler. If task registration fails, JARVIS reports the issue and its in-app reminder checker still works while the app remains running (including in the system tray). Uninstall removes JARVIS reminder tasks and its optional Windows sign-in startup entry; the local reminder database is preserved.

## Live web search, weather and news

When internet is available, JARVIS can answer these commands directly without an AI API key:

- `search web for Python tutorials` (also `search for ...` or `google ...`)
- `weather in Bhopal` (also `mausam Bhopal`; ask for a city if omitted)
- `latest news`, `news about technology`

Web search uses DuckDuckGo's HTML results, headlines use Google News RSS with India editions, and current conditions use Open-Meteo geocoding and forecast APIs. These public services do not require a separate key or paid package. Online requests use HTTPS, a 12-second timeout, and a response-size limit. Search/news results include source links; JARVIS does not execute page content or arbitrary commands. Live services require internet and do not work offline. Weather lookup needs a city name rather than assuming the Windows PC's location.

## Offline PC health status

Ask or type `system status`, `PC status`, `system health`, or `system status batao` to get a read-only snapshot of CPU, memory, system-drive usage, battery/charging state, network-interface status, and uptime. This uses the locally installed psutil package and works without internet. Hardware sensors that Windows does not expose are reported as unavailable; this command does not change system settings or run shell commands.

## Search for and open local files

Type or say `find file budget`, `look for file budget`, `file dhundo notes`, `file dhoondho notes`, or `फाइल ढूँढो report`. Choose a folder when prompted; JARVIS searches filenames only (not file contents), skips hidden files and symlinks, and caps work at 50 results / 5,000 directories. After a search, say or type `open file 2` (also `open the second file`, `second result kholo`, `file khol do 2`, or `दूसरी फाइल खोलो`) to select a numbered result from the latest search. JARVIS asks for confirmation before opening it with the Windows default application. For safety, only supported document and media formats are eligible; executables, scripts, shortcuts, and web shortcut files are not opened through search results. If a result was moved or deleted, JARVIS refuses to open it.

## Read local documents offline

Type `read file` (or `document kholo`) in the JARVIS command bar and choose a file. JARVIS extracts text locally from PDF, Word DOCX, TXT, Markdown, CSV, JSON, common code and other text files. The selected document is not uploaded. After reading, you can ask JARVIS to summarize or explain it; that separate AI request uses your configured online AI service and sends the relevant conversation text. PDF extraction supports selectable text, not scanned-image OCR. Reads are limited to 15 MB, 100 PDF pages, and 40,000 extracted characters; the chat preview is capped at 12,000 characters.

## Updates

JARVIS checks the official GitHub Releases page once at startup. You can also use **SETTINGS → Check for updates** to check manually. JARVIS downloads the installer only after confirmation, verifies its SHA-256 against the release checksum file, and asks before launching the installer. Updates are published from version tags (`v1.1.0`, etc.); checking for updates reports that no stable release exists until the first tagged release is published.

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

Press **Save settings**. To test without a Picovoice key, type a message and press **Send**; wake listening requires a separate Picovoice AccessKey. The main window shows the blue holographic command dashboard with an animated reactor, resource panel, quick-access folders, and voice/chat controls. Use CHAT LOG to open the conversation transcript and SETTINGS to configure the backend, wake-word key, and optional Windows sign-in startup. Closing the main window moves JARVIS to the Windows system tray; use the tray menu to reopen it, activate/stop voice listening, or fully exit. The startup option adds/removes a per-user Windows Run registry entry and does not require administrator access. Conversations are saved in `%APPDATA%\\JARVISDesktop\\chat_history.json`; personal memories are stored separately in `%LOCALAPPDATA%\\JARVISDesktop\\memory.sqlite3` and remain available offline. Say `remember that I prefer Hinglish`, `what do you remember`, or open CHAT LOG → Manage memory to add, edit, and delete saved memories. Memory capture is explicit; JARVIS does not silently save arbitrary chat content. Passwords, API keys, tokens, OTPs, and secrets are blocked. Sharing saved memories with online AI chats is off by default and can be enabled in Settings. Clear conversation does not delete personal memories. Voice and typed Windows commands ignore polite prefixes such as `please`, `hey Jarvis`, `can you`, and `zara`, plus courtesy endings such as `please` or `now`; the final action must still exactly match the safe command allowlist. Exact commands currently supported include `open notepad`, `open calculator`, `open downloads`, `open downloads folder`, `open file explorer`, `open task manager`, `open browser`, `open google`, `open youtube`, `volume up`, `volume down`, `mute`, `play pause`, `next track`, and `previous track`, `brightness up`, and `brightness down`. Media/volume actions use fixed Windows multimedia key events; brightness changes use 10-point steps on the primary supported display; arbitrary shell commands are not executed. The dashboard POWER control opens a confirmation dialog for shutdown/restart; both are scheduled 60 seconds ahead and can be cancelled from the same dialog. These actions are never triggered by an unconfirmed chat phrase. Say “Jarvis”, wait for the listening status, then speak a command. After wake detection, the microphone checks for a command in cancellable one-second start-of-phrase intervals; stopping during an already-started phrase may still wait until the current phrase capture ends (up to the configured 12-second phrase limit). You can also send a typed message without enabling the microphone.

Keys are stored using the Windows Credential Manager through Python's `keyring` package. The endpoint and model are stored in the current user's AppData folder. Do not put keys in source files, screenshots, or Git commits.

## Build a Windows executable

From the same folder, after installing requirements:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name JARVIS jarvis_desktop.py
```

The executable is written to `dist\JARVIS.exe`. Keep the original `requirements.txt` and this guide for maintenance. Some endpoint/microphone/Picovoice configurations can require troubleshooting on the target PC.

## Current scope and limitations

- This Windows edition has its own UI, settings, voice loop, and local chat history. It does not sync its history or settings with the separate Android edition.
- Speech recognition supports online Google transcription with local Vosk fallback. JARVIS automatically prepares the selected small model in the background while online; Hindi (India), English (India), and English (US) have separate offline models. Hindi/Hinglish recognition quality depends on the selected model and accent; mixed-language accuracy is not guaranteed. AI replies and web/AI features still require internet. Use STOP SPEECH on the dashboard or Stop speaking in the tray menu to interrupt spoken replies.
- Test the microphone and wake word on the actual Windows laptop before relying on continuous listening.


## Automated installer artifact

The Windows CI builds both a portable `JARVIS.exe` and an Inno Setup installer named `JARVIS-Setup-x64.exe`. After a successful `Windows Desktop Checks` workflow, download the `JARVIS-Windows-Installer-x64` artifact from the run's Artifacts section. The installer creates a Start Menu shortcut and offers an optional Desktop shortcut. It installs per-user without administrator privileges; automatic startup is opt-in from SETTINGS and can be disabled there.
