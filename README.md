# JARVIS Desktop for Windows 11

This repository currently contains the native Windows laptop edition of JARVIS. The Android edition is maintained separately. It provides a blue JARVIS-themed command dashboard, separate conversation window, text input, spoken replies, persistent local chat history, offline-first private personal memory, a small allowlist of safe Windows app/website commands, and optional always-listening, local wake-word detection using openWakeWord and a single-word Jarvis ONNX model.

On first launch, JARVIS shows a foreground consent prompt for microphone use; upgrading to the current build re-asks once so older saved choices cannot silently suppress the prompt. If microphone access is accepted, JARVIS checks the default input device and releases it immediately; continuous voice listening still starts only when you activate it. If Windows blocks microphone access, JARVIS offers **Settings → Privacy & security → Microphone**. Windows controls the system-wide **Let desktop apps access your microphone** privacy switch; JARVIS never bypasses Windows privacy controls. Windows sign-in startup is optional and uses the current user's settings; it does not require elevation.

## Requirements

- Windows 10/11, 64-bit
- Python 3.11 (recommended)
- Microphone and speakers/headphones (microphone access is optional until you enable voice setup; Windows controls the permission)
- Internet for live web search, weather, news, and the separately licensed wake-word classifier/runtime assets; the installer bundles offline Vosk speech models and the owner-speaker encoder
- Offline AI: the full offline installer already includes the Ollama runtime and `qwen3.5:4b` model assets (approximately 3.3–4.0 GB). Installation verifies the bundled model and runs a local inference check; no separate model download is required.
- A user-installed, license-compatible Jarvis ONNX wake-word classifier; the publisher model is not redistributed in the public installer ([details](docs/guides/JARVIS_WAKEWORD_SETUP.md)); custom-model training and import are documented in [WAKEWORD_FIRST_PARTY_MODEL.md](docs/guides/WAKEWORD_FIRST_PARTY_MODEL.md)
- Internet access is not required for local Qwen chat or offline Vosk transcription after installation; the separately licensed wake-word model/runtime and live web services may require internet. No API key or cloud AI backend is used for general AI chat

Wake-word inference runs locally through openWakeWord after its separately licensed ONNX classifier and shared feature files are installed; no Picovoice account, AccessKey, or cloud wake-word service is required. The classifier is not redistributed in the public installer because the publisher's default terms restrict use and redistribution; review the license and complete the in-app setup before relying on wake-word activation. Voice activation also requires an enrolled local owner speaker profile ([setup](docs/guides/OWNER_VOICE_SETUP.md)); voice matching is not strong authentication. The installer bundles the pinned ECAPA speaker encoder, but enrollment remains an explicit local action and the user's derived voice profile is never bundled. Run `py wakeword_mic_test.py` from `desktop/windows` to perform a local quiet-room, spoken-wake-word, and background-noise microphone check; the test does not save or upload audio. Speech transcription tries Google's online recognizer first and falls back to the bundled local Vosk model when the network request fails or the audio is unclear. Hindi, Indian English, and US English Vosk models are included in the installer, so offline transcription does not require a first-use model download. Online recognition requests have an eight-second network timeout. The Vosk model archives are listed as Apache-2.0 by Alpha Cephei; their license text is included with the installer. The desktop app does not hide or bypass Windows microphone privacy indicators.

## 3D hologram

The HUD includes an animated Three.js reactor overlay. The hologram runs locally inside the JARVIS desktop window and does not need webcam access.

Voice examples include “Jarvis Chrome kholo”, “Google Chrome kholo”, “volume kam kar do”, and “awaaz badhao”. Local desktop actions remain restricted to the fixed allowlist.


## Safe agent actions and approval boundaries

The AI tool layer supports user-directed multi-step browser automation through `desktop/windows/browser_automation.py`. After each action, JARVIS reads the newly rendered page and asks local Qwen to plan the next small batch; it stops on completion, authorization denial, repeated no-progress page state, errors, or a 10-minute safety time budget. It opens a visible Microsoft Edge session on Windows (with Playwright Chromium fallback) using a dedicated JARVIS profile, not the user's everyday browser profile. Every action still passes the existing browser safety checks.

- **Website interaction:** open public HTTPS sites, open/switch tabs, read pages, click one unambiguous visible element, navigate, and scroll. Ordinary navigation and non-sensitive clicks do not ask for voice permission.
- **Form automation:** fill ordinary search and form fields, choose dropdown options, and use navigation keys. JARVIS never enters passwords, PINs, OTPs, API tokens, payment-card secrets, personal contact details, addresses, or identity data; enter those yourself in the visible browser. Pressing Enter to submit a non-search form, or clicking a control identified as sensitive, requires exact one-time spoken approval.
- **Email and messaging:** `send_email` supports configured Gmail and Microsoft Graph; `send_message` supports Telegram Bot API and official WhatsApp Cloud API. The exact recipient and final content are read aloud and a one-time voice approval is consumed immediately before sending. The user must explicitly request sending; drafting text alone never sends it.
- **File operations:** safe downloads are saved in the Windows Downloads folder, limited to 50 MB, and executable/script file types are blocked. Uploads are limited to one user-selected file from Desktop, Documents, or Downloads, up to 25 MB, and require exact one-time voice approval.
- **Shopping research:** JARVIS can navigate product pages, search, read product details, and compare options. Checkout controls, cart actions, purchases, and payments are deliberately disabled; it will stop before placing an order or entering financial details.

Sensitive approvals are bound to the exact action details, expire quickly, and can be used once. Ordinary website navigation, page reading, searching, and non-sensitive form filling do not ask for permission. If microphone consent or trusted voice approval is unavailable, a sensitive action is blocked.

Provider setup is local. Supply pre-authorized access tokens through Windows Credential Manager (service `JARVIS-Desktop`) or the process environment: `JARVIS_GMAIL_ACCESS_TOKEN` and `JARVIS_GMAIL_USER`; `JARVIS_GRAPH_ACCESS_TOKEN`; `JARVIS_TELEGRAM_BOT_TOKEN`; or `JARVIS_WHATSAPP_ACCESS_TOKEN`, `JARVIS_WHATSAPP_PHONE_NUMBER_ID`, and `JARVIS_WHATSAPP_API_VERSION`. JARVIS does not perform provider OAuth sign-in or refresh expired access tokens; obtain authorization only through each provider's official flow. Keep credentials out of chat and source control. WhatsApp messages must comply with Meta's business messaging rules.

Playwright is installed with the desktop requirements. On Windows, JARVIS first attempts to use the installed Microsoft Edge browser; if that is unavailable, install the managed Chromium runtime with `py -m playwright install chromium` from the `desktop/windows` environment. Browser profile data is stored separately under the JARVIS app-data folder. Arbitrary shell commands, unrestricted file deletion, live checkout, purchases, payments, and account/security mutations are not available.

The existing native file-removal flow only moves explicitly selected files from approved folders to the Windows Recycle Bin. Never provide passwords, API keys, PINs, or one-time codes to JARVIS.

## Hybrid online and offline AI

General AI chat always uses the same local Ollama model, `qwen3.5:4b`, whether the PC is online or offline. Local requests go only to `127.0.0.1:11435`; they do not require an API key, cloud AI gateway, or JARVIS backend. Internet is used separately for live web search, weather, and news. Local requests use a bounded context and reply length to reduce memory pressure on 8 GB laptops. Live internet features are unavailable while offline.

**Automatic model setup:**

The full offline installer already contains the Ollama runtime and Qwen3.5 4B model files. During installation, JARVIS automatically verifies the bundled files, starts its private local Ollama service, and runs a real inference check. There is no optional or deferred model-download step, and no separate model download is needed. If the bundled model is missing or fails verification, setup stops with an error instead of silently downloading a replacement.

After setup, general AI chat uses local Qwen3.5 4B in both online and offline modes. Live web search, weather, and news separately require internet. If Windows restarts and Ollama is not running, JARVIS attempts to start its local service when needed. Response quality and speed depend on available RAM/CPU; close other memory-heavy apps if an 8 GB PC struggles.

## Offline reminders

JARVIS can create local reminders by typing or speaking commands such as:

- `remind me in 10 minutes to drink water`
- `remind me at 18:30 to call home`
- `mujhe 2 ghante baad meeting yaad dilana`
- `show reminders`
- `delete reminder 3`

Reminders are stored in `%LOCALAPPDATA%\\JARVISDesktop\\reminders.sqlite3` and work without internet. Due-time checks compare absolute timestamps, so reminders remain correctly ordered even when saved timestamps contain different UTC offsets or daylight-saving changes. On Windows, JARVIS registers a one-shot, current-user Task Scheduler task for each reminder. A small notification-only JARVIS process displays a native Windows reminder dialog even when the main app is closed. The user must still be signed in and the PC must be awake; reminders cannot wake a powered-off PC, and delivery after sleep depends on Windows Task Scheduler. If task registration fails, JARVIS reports the issue and its in-app reminder checker still works while the app remains running (including in the system tray). Uninstall removes JARVIS reminder tasks and its optional Windows sign-in startup entry; the local reminder database is preserved.

## Live web search, weather and news

When internet is available, JARVIS can answer these commands directly without an AI API key:

- `search web for Python tutorials` (also `search for ...` or `google ...`)
- `weather in Bhopal` (also `mausam Bhopal`; ask for a city if omitted)
- `latest news`, `news about technology`

Web search uses DuckDuckGo's HTML results, headlines use Google News RSS with India editions, and current conditions use Open-Meteo geocoding and forecast APIs. These public services do not require a separate key or paid package. Online requests use HTTPS, a 12-second timeout, and a response-size limit. Search/news results include source links; JARVIS does not execute page content or arbitrary commands. Live services require internet and do not work offline. Weather lookup needs a city name rather than assuming the Windows PC's location.

## Offline PC health status

Ask or type `system status`, `PC status`, `system health`, or `system status batao` to get a read-only snapshot of CPU, memory, system-drive usage, battery/charging state, network-interface status, and uptime. This uses the locally installed psutil package and works without internet. Hardware sensors that Windows does not expose are reported as unavailable; this command does not change system settings or run shell commands.

## Focus Mode, workflows and recurring automations

These features run locally and use a small SQLite database in the JARVIS app-data folder.

- **Focus Mode / Pomodoro:** say `start pomodoro`, `start focus for 45 minutes`, `focus status`, or `stop focus`. Sessions persist across app restarts.
- **Smart workflows:** `run study workflow`, `run meeting workflow`, or `run deep work workflow`. Workflows only launch fixed, allowlisted apps (Notepad, Calculator, browser, Task Manager); no shell commands or arbitrary scripts.
- **Recurring automation:** `repeat study workflow every 60 minutes`, `list automations`, or `delete automation 1`. Intervals are limited to 5 minutes–7 days. If a workflow launch fails, JARVIS schedules a retry in five minutes instead of silently losing that run. Automations run while JARVIS is running (including its tray mode); they are not guaranteed while Windows/JARVIS is shut down.

## Live process and app resource usage

Ask JARVIS `top processes`, `show top processes`, or `which apps use most RAM` to see a read-only snapshot of the processes using the most memory, including each process's PID and current CPU/RAM percentages. JARVIS skips processes Windows does not allow it to inspect and limits the report to five entries. This feature never terminates, changes, or launches a process and works locally without an AI API key.

## Search for and open local files

Type or say `find file budget`, `look for file budget`, `file dhundo notes`, `file dhoondho notes`, or `फाइल ढूँढो report`. Choose a folder when prompted; JARVIS searches filenames only (not file contents), skips hidden files and symlinks, and caps work at 50 results / 5,000 directories. After a search, say or type `open file 2` (also `open the second file`, `second result kholo`, `file khol do 2`, or `दूसरी फाइल खोलो`) to select a numbered result from the latest search. JARVIS asks for confirmation before opening it with the Windows default application. For safety, only supported document and media formats are eligible; executables, scripts, shortcuts, and web shortcut files are not opened through search results. If a result was moved or deleted, JARVIS refuses to open it.

## Read local documents offline

Type `read file` (or `document kholo`) in the JARVIS command bar and choose a file. JARVIS extracts text locally from PDF, Word DOCX, TXT, Markdown, CSV, JSON, common code and other text files. The selected document is not uploaded. For AI help, type `summarize document` or `ask document what is the invoice date` (also `document se pucho invoice date kya hai`) and select the file. JARVIS explains that the extracted text will be processed by the local Qwen model and asks permission before proceeding. If you decline, the file stays local. Document text and AI answers are not persisted in chat history. PDF extraction supports selectable text, not scanned-image OCR. Reads are limited to 15 MB, 100 PDF pages, and 40,000 extracted characters; the chat preview is capped at 12,000 characters.

## Updates

JARVIS checks the official rolling Windows release once at startup. You can also use **SETTINGS → Check for updates** to check manually. Main-branch Windows builds publish to the `jarvis-latest` prerelease with a unique build version, installer, `JARVIS-Portable-x64.zip` (the complete onedir app), JARVIS downloads the installer only after confirmation, verifies its SHA-256 against GitHub's release-asset digest, and asks before launching the installer. Version-tagged releases (`v1.1.0`, etc.) remain available as separate manual releases.

## Run from source

Open PowerShell in this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
cd desktop\\windows
pip install -r requirements.txt
python jarvis_desktop.py
```

On first launch, JARVIS does not need to register with a remote backend for general AI chat. The local Qwen3.5 4B model runs through Ollama on this PC. No account, API key, or remote AI gateway is required for general chat. Live web services use public endpoints and require internet access.

For optional wake-word listening, install the single-word Jarvis ONNX model by following [JARVIS_WAKEWORD_SETUP.md](docs/guides/JARVIS_WAKEWORD_SETUP.md). The wake-word detector then runs locally; there is no wake-word API key to configure. General AI chat uses the local Qwen3.5 4B model and does not need endpoint configuration or a backend token.

To test without a wake-word model installed, type a message and press **Send**; voice listening requires the Jarvis ONNX model described in [JARVIS_WAKEWORD_SETUP.md](docs/guides/JARVIS_WAKEWORD_SETUP.md). The main window shows the blue holographic command dashboard with an animated reactor, resource panel, quick-access folders, and voice/chat controls. Use CHAT LOG to open the conversation transcript and SETTINGS to configure available local preferences and optional Windows sign-in startup. Closing the main window moves JARVIS to the Windows system tray; use the tray menu to reopen it, activate/stop voice listening, or fully exit. The startup option adds/removes a per-user Windows Run registry entry and does not require administrator access. Conversations are saved in `%APPDATA%\\JARVISDesktop\\chat_history.json`; personal memories are stored separately in `%LOCALAPPDATA%\\JARVISDesktop\\memory.sqlite3` and remain available offline. Say `remember that I prefer Hinglish`, `what do you remember`, or open CHAT LOG → Manage memory to add, edit, and delete saved memories. Memory capture is explicit; JARVIS does not silently save arbitrary chat content. Passwords, API keys, tokens, OTPs, and secrets are blocked. Sharing saved memories with AI chats is off by default and can be enabled in Settings. Clear conversation does not delete personal memories. Voice and typed Windows commands ignore polite prefixes such as `please`, `hey Jarvis`, `can you`, and `zara`, plus courtesy endings such as `please` or `now`; the final action must still exactly match the safe command allowlist. Exact commands currently supported include `open notepad`, `open calculator`, `open downloads`, `open downloads folder`, `open file explorer`, `open task manager`, `open browser`, `open google`, `open youtube`, `volume up`, `volume down`, `mute`, `play pause`, `next track`, and `previous track`, `brightness up`, and `brightness down`. Media/volume actions use fixed Windows multimedia key events; brightness changes use 10-point steps on the primary supported display; arbitrary shell commands are not executed. The dashboard POWER control opens a confirmation dialog for shutdown/restart; both are scheduled 60 seconds ahead and can be cancelled from the same dialog. These actions are never triggered by an unconfirmed chat phrase. Say “Jarvis”, wait for the listening status, then speak a command. After wake detection, the microphone checks for a command in cancellable one-second start-of-phrase intervals; stopping during an already-started phrase may still wait until the current phrase capture ends (up to the configured 12-second phrase limit). You can also send a typed message without enabling the microphone.

General AI chat has no API-key, endpoint, or cloud-provider settings: both online and offline chat use local Ollama `qwen3.5:4b`. Windows Credential Manager is used only by separate local voice-profile and optional connected-service features; those credentials are not used for general chat.

## Build a Windows executable

From `desktop/windows`, after installing requirements:

```powershell
pyinstaller --noconfirm --clean --onedir --windowed --add-data "jarvis_hud.html;." --collect-all webview --collect-all bottle --collect-all proxy_tools --collect-all pystray --collect-all PIL --collect-all vosk --name JARVIS jarvis_desktop.py
```

The application is written to `dist\\JARVIS\\` (run `dist\\JARVIS\\JARVIS.exe`). Keep the complete folder together; the HUD and collected WebView/runtime dependencies are required. This matches the automated Windows build and installer. Some endpoint, microphone, or ONNX model configurations can require troubleshooting on the target PC.

## Current scope and limitations

- This Windows edition has its own UI, settings, voice loop, and local chat history. It does not sync its history or settings with the separate Android edition.
- Speech recognition supports online Google transcription with local Vosk fallback. JARVIS automatically prepares the selected small model in the background while online; Hindi (India), English (India), and English (US) have separate offline models. Hindi/Hinglish recognition quality depends on the selected model and accent; mixed-language accuracy is not guaranteed. Live web services require internet; after the one-time Ollama model setup, general AI chat uses the same local model online and offline. AI API responses are capped at 2 MB to prevent unexpectedly large payloads from exhausting desktop memory. Use STOP SPEECH on the dashboard or Stop speaking in the tray menu to interrupt spoken replies.
- Test the microphone and wake word on the actual Windows laptop before relying on continuous listening.


## Automated installer artifact

The Windows CI builds a portable `JARVIS\\` application folder (containing `JARVIS.exe` and its runtime files) and an Inno Setup installer named `JARVIS-Setup-x64.exe`. After a successful `JARVIS Project Checks and Windows Build` workflow, download the `JARVIS-Windows-Installer-x64` artifact from the run's Artifacts section. The portable artifact is named `JARVIS-Windows-Portable-x64` and must be extracted as a complete folder. The installer creates a Start Menu shortcut and offers an optional Desktop shortcut. It installs per-user without administrator privileges; automatic startup is opt-in from SETTINGS and can be disabled there.
