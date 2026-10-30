"""Native Windows companion app for JARVIS.

Keys are stored in Windows Credential Manager via keyring, never in the settings JSON.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "JARVIS"
KEYRING_SERVICE = "JARVIS-Desktop"
SETTINGS_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "JARVISDesktop"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
HISTORY_FILE = SETTINGS_DIR / "chat_history.json"
DEFAULT_ENDPOINT = "https://jarvis-backend-zqlw.onrender.com/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
SYSTEM_PROMPT = (
    'You are J.A.R.V.I.S., a calm, polished personal AI butler with subtle dry wit. '
    'Support Hindi, English, and Hinglish. Match the language and script used by the user. '
    'Be concise when the reply will be spoken aloud. Never claim an action succeeded unless it did.'
)


def load_settings() -> dict:
    defaults = {"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL, "language": "en-IN"}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            settings = {**defaults, **data}
            # Older installs used OpenRouter directly. Migrate them to the secured JARVIS gateway.
            if settings.get("endpoint", "").strip() == "https://openrouter.ai/api/v1/chat/completions":
                settings["endpoint"] = DEFAULT_ENDPOINT
                try:
                    save_settings(settings)
                except OSError:
                    pass
            return settings
    except (OSError, ValueError):
        pass
    return defaults


def save_settings(data: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_chat_history(path: Path = HISTORY_FILE) -> list[dict]:
    """Load a bounded, validated chat history; corrupt files are ignored safely."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    clean = []
    for item in data[-100:]:
        if (isinstance(item, dict) and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("content"), str)):
            content = item["content"].strip()
            if content:
                clean.append({"role": item["role"], "content": content[:12000]})
    return clean


def save_chat_history(history: list[dict], path: Path = HISTORY_FILE) -> None:
    """Atomically persist only chat roles and text, never credentials or settings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = [
        {"role": item["role"], "content": str(item["content"])[:12000]}
        for item in history[-100:]
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
    ]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_local_command(command: str, popen=None, open_url=None) -> str | None:
    """Run only fixed, explicitly allowlisted desktop actions; never invoke a shell."""
    import subprocess
    import webbrowser

    launch = popen or subprocess.Popen
    browse = open_url or webbrowser.open
    normalized = " ".join(command.casefold().strip().rstrip(" .!?").split())
    actions = {
        "open notepad": ("app", ["notepad.exe"], "Opening Notepad."),
        "start notepad": ("app", ["notepad.exe"], "Opening Notepad."),
        "open calculator": ("app", ["calc.exe"], "Opening Calculator."),
        "open calc": ("app", ["calc.exe"], "Opening Calculator."),
        "open file explorer": ("app", ["explorer.exe"], "Opening File Explorer."),
        "open explorer": ("app", ["explorer.exe"], "Opening File Explorer."),
        "open task manager": ("app", ["taskmgr.exe"], "Opening Task Manager."),
        "open taskmanager": ("app", ["taskmgr.exe"], "Opening Task Manager."),
        "open browser": ("url", "https://www.google.com", "Opening your default browser."),
        "open google": ("url", "https://www.google.com", "Opening Google."),
        "open youtube": ("url", "https://www.youtube.com", "Opening YouTube."),
    }
    media_actions = {
        "volume up": ("volume_up", "Volume increased."),
        "increase volume": ("volume_up", "Volume increased."),
        "volume down": ("volume_down", "Volume decreased."),
        "decrease volume": ("volume_down", "Volume decreased."),
        "mute": ("volume_mute", "Volume mute state toggled."),
        "unmute": ("volume_mute", "Volume mute state toggled."),
        "play pause": ("play_pause", "Media playback toggled."),
        "pause music": ("play_pause", "Media playback toggled."),
        "resume music": ("play_pause", "Media playback toggled."),
        "next track": ("next_track", "Skipping to the next track."),
        "previous track": ("previous_track", "Going to the previous track."),
    }
    if normalized in media_actions:
        key_name, response = media_actions[normalized]
        if not press_windows_media_key(key_name):
            raise RuntimeError("Windows media controls are available only on Windows.")
        return response
    action = actions.get(normalized)
    if action is None:
        return None
    kind, target, response = action
    if kind == "app":
        launch(target, shell=False)
    else:
        if browse(target) is False:
            raise RuntimeError("Windows could not open the requested website.")
    return response


def schedule_windows_power_action(action: str, popen=None, platform_name=None) -> bool:
    """Schedule a fixed Windows power action with a 60-second cancellation window."""
    import os as _os
    import subprocess

    if (platform_name or _os.name) != "nt":
        return False
    commands = {
        "shutdown": ["shutdown.exe", "/s", "/t", "60"],
        "restart": ["shutdown.exe", "/r", "/t", "60"],
        "cancel": ["shutdown.exe", "/a"],
    }
    command = commands.get(action)
    if command is None:
        return False
    (popen or subprocess.Popen)(command, shell=False)
    return True


def press_windows_media_key(key_name: str, keybd_event=None, platform_name=None) -> bool:
    """Send one fixed Windows multimedia key; never accepts arbitrary key codes."""
    import ctypes
    import os as _os

    if (platform_name or _os.name) != "nt":
        return False
    keys = {
        "volume_up": 0xAF,
        "volume_down": 0xAE,
        "volume_mute": 0xAD,
        "play_pause": 0xB3,
        "next_track": 0xB0,
        "previous_track": 0xB1,
    }
    code = keys.get(key_name)
    if code is None:
        return False
    sender = keybd_event or ctypes.windll.user32.keybd_event
    sender(code, 0, 0, 0)
    sender(code, 0, 2, 0)
    return True


STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def build_startup_command(executable=None, script_path=None, frozen=None) -> str:
    """Build a safely quoted per-user startup command for frozen or Python runs."""
    import subprocess

    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    app_executable = executable or sys.executable
    if is_frozen:
        parts = [app_executable]
    else:
        executable_path = Path(app_executable)
        pythonw = executable_path.with_name("pythonw.exe")
        runner = str(pythonw if pythonw.exists() else executable_path)
        parts = [runner, str(script_path or Path(__file__).resolve())]
    return subprocess.list2cmdline(parts)


def set_windows_startup(enabled: bool, winreg_module=None, executable=None,
                        script_path=None, frozen=None, platform_name=None) -> bool:
    """Enable or disable JARVIS for the current Windows user (no elevation)."""
    import os as _os

    if (platform_name or _os.name) != "nt":
        raise RuntimeError("Windows startup settings are available only on Windows.")
    if winreg_module is None:
        import winreg as winreg_module
    key = winreg_module.CreateKey(
        winreg_module.HKEY_CURRENT_USER, STARTUP_RUN_KEY
    )
    try:
        if enabled:
            command = build_startup_command(executable, script_path, frozen)
            winreg_module.SetValueEx(
                key, APP_NAME, 0, winreg_module.REG_SZ, command
            )
        else:
            try:
                winreg_module.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg_module.CloseKey(key)
    return True


def speak_text_interruptibly(text: str, stop_event, engine_factory=None) -> bool:
    """Speak on the calling worker thread while allowing the UI to interrupt playback."""
    import time
    if engine_factory is None:
        import pyttsx3
        engine_factory = pyttsx3.init
    engine = engine_factory()
    try:
        engine.say(text)
        engine.startLoop(False)
        try:
            while engine.isBusy() and not stop_event.is_set():
                engine.iterate()
                time.sleep(0.01)
            if stop_event.is_set():
                engine.stop()
                return False
            return True
        finally:
            engine.endLoop()
    finally:
        try:
            engine.stop()
        except Exception:
            pass


def chat_completion(endpoint: str, model: str, api_key: str, prompt: str,
                    history: list[dict]) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(endpoint.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("AI endpoint must be a valid HTTPS URL without embedded credentials.")
    if not model.strip() or not api_key.strip():
        raise ValueError("Please set the AI model and API key in Settings.")

    language_hint = (
        "Reply in Hindi (Devanagari) if the user writes Hindi in Devanagari, "
        "in English if the user writes English, and in Hinglish (Roman script) if the user writes Hinglish."
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": language_hint}]
    messages.extend(history[-16:])
    messages.append({"role": "user", "content": prompt})
    payload = json.dumps({
        "model": model.strip(),
        "messages": messages,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint.strip(), data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key.strip()}",
                 "Content-Type": "application/json"},
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise RuntimeError("The AI endpoint redirected the request; redirects are blocked for API-key safety.") from exc
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"AI endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the AI endpoint: {exc.reason}") from exc

    try:
        result = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("The AI endpoint returned an unexpected response format.") from exc
    if isinstance(result, list):
        result = " ".join(str(part.get("text", "")) for part in result if isinstance(part, dict))
    result = str(result).strip()
    return result or "I received an empty response, Sir."


class JarvisDesktop:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("J.A.R.V.I.S. | Desktop Assistant")
        self.root.geometry("900x700")
        self.root.minsize(720, 560)
        self.root.configure(bg="#07111b")
        self.settings = load_settings()
        self.events: queue.Queue = queue.Queue()
        self.history: list[dict] = load_chat_history()
        self.stop_event = threading.Event()
        self.wake_thread: threading.Thread | None = None
        self.busy = False
        self.tray_icon = None
        self.tray_thread = None
        self.speech_stop_event = threading.Event()
        # Serialize typed and voice requests so history and TTS cannot race.
        self.request_lock = threading.Lock()

        try:
            import keyring
            self.keyring = keyring
        except Exception:
            self.keyring = None

        self._build_ui()
        self._load_secrets()
        # Snapshot secrets as plain strings so worker threads never call Tk variables.
        self.ai_api_key = self.api_key_var.get()
        self.picovoice_access_key = self.picovoice_var.get()
        self.root.after(120, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    def _build_ui(self):
        """Build the blue holographic laptop dashboard while keeping the assistant controls live."""
        self.root.title("J.A.R.V.I.S. | Desktop Command Center")
        self.root.geometry("1500x900")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#02070d")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("HUD.TButton", background="#061827", foreground="#8deeff",
                        bordercolor="#087ca8", padding=(12, 8), font=("Segoe UI", 10))
        style.map("HUD.TButton", background=[("active", "#0a2940")])
        style.configure("HUD.TEntry", fieldbackground="#04111d", foreground="#d9faff",
                        insertcolor="#ffffff", bordercolor="#087ca8", padding=9)
        self.hud = tk.Canvas(self.root, bg="#02070d", highlightthickness=0)
        self.hud.pack(fill="both", expand=True)
        self.hud.bind("<Configure>", lambda _event: self._draw_orb())
        self.orb_phase = 0.0
        self.status_var = tk.StringVar(value="SYSTEM ONLINE  •  JARVIS READY")
        self.chat = None
        self.transcript = [("YOU" if item["role"] == "user" else "JARVIS", item["content"], None) for item in self.history]
        self.prompt_var = tk.StringVar()
        self.prompt_entry = ttk.Entry(self.root, textvariable=self.prompt_var, style="HUD.TEntry")
        self.send_button = ttk.Button(self.root, text="TRANSMIT  ➤", style="HUD.TButton", command=self.send_text)
        self.stop_speaking_button = ttk.Button(self.root, text="STOP SPEECH", style="HUD.TButton",
                                               command=self.stop_speaking)
        self.listen_button = ttk.Button(self.root, text="◉  ACTIVATE VOICE", style="HUD.TButton",
                                        command=self.toggle_listening)
        self.chat_button = ttk.Button(self.root, text="CHAT LOG", style="HUD.TButton", command=self.open_chat)
        self.settings_button = ttk.Button(self.root, text="SETTINGS ⚙", style="HUD.TButton", command=self.open_settings)
        self.power_button = ttk.Button(self.root, text="POWER", style="HUD.TButton", command=self.open_power_controls)
        self.prompt_entry.bind("<Return>", lambda _event: self.send_text())
        self._draw_orb()
        self.root.after(50, self._animate_orb)

    def _animate_orb(self):
        if not self.root.winfo_exists():
            return
        self.orb_phase = (self.orb_phase + 1.2) % 360.0
        self._draw_orb()
        self.root.after(55, self._animate_orb)

    def _get_service_statuses(self):
        """Report readiness from actual configuration and installed capabilities."""
        import importlib.util

        ai_ready = bool(getattr(self, "ai_api_key", "").strip())
        voice_key_ready = bool(getattr(self, "picovoice_access_key", "").strip())
        voice_packages = all(
            importlib.util.find_spec(module) is not None
            for module in ("pvporcupine", "pvrecorder", "speech_recognition", "pyttsx3")
        )
        return [
            ("AI CHAT", ai_ready, "CONFIGURED" if ai_ready else "ADD API TOKEN"),
            ("VOICE ENGINE", voice_key_ready and voice_packages,
             "CONFIGURED" if voice_key_ready and voice_packages else "SETUP REQUIRED"),
            ("MEMORY", True, "LOCAL HISTORY"),
            ("SYSTEM CONTROL", os.name == "nt",
             "WINDOWS" if os.name == "nt" else "WINDOWS ONLY"),
        ]

    def _draw_orb(self):
        if not hasattr(self, "hud"):
            return
        import math
        from datetime import datetime
        c = self.hud
        w, h = max(c.winfo_width(), 1100), max(c.winfo_height(), 700)
        c.delete("all")
        c.configure(bg="#02070d")
        blue, bright, dim = "#00bfff", "#8af4ff", "#075477"
        phase = math.radians(self.orb_phase)
        c.create_rectangle(0, 0, w, h, fill="#02070d", outline="")
        # Fine HUD grid and edge frame
        for x in range(0, w, 48):
            c.create_line(x, 0, x, h, fill="#041522")
        for y in range(0, h, 48):
            c.create_line(0, y, w, y, fill="#041522")
        c.create_rectangle(14, 14, w-14, h-14, outline="#075477", width=1)
        c.create_line(24, 62, w-24, 62, fill=blue, width=2)
        c.create_text(42, 35, text="◈  J A R V I S", fill=bright, anchor="w",
                      font=("Segoe UI Semibold", 21))
        c.create_text(250, 36, text="PERSONAL COMMAND INTERFACE  /  V 1.0",
                      fill="#328aa8", anchor="w", font=("Consolas", 9))
        c.create_window(w-365, 35, window=self.chat_button, width=105, height=30)
        c.create_window(w-250, 35, window=self.settings_button, width=115, height=30)
        c.create_window(w-125, 35, window=self.power_button, width=90, height=30)
        c.create_oval(w-480, 25, w-468, 37, fill="#00f0a0", outline="")
        c.create_text(w-455, 31, text="SYSTEM ONLINE", fill=bright, anchor="w",
                      font=("Consolas", 10, "bold"))
        # Panel helper
        def panel(x1, y1, x2, y2, title):
            c.create_rectangle(x1, y1, x2, y2, fill="#03101b", outline="#087ca8", width=1)
            c.create_line(x1+12, y1, x1+145, y1, fill=bright, width=2)
            c.create_text(x1+14, y1+13, text=title, fill=bright, anchor="w",
                          font=("Consolas", 10, "bold"))
        left, right = 28, 290
        panel(left, 88, 260, 278, "DATE / TIME")
        now = datetime.now()
        c.create_text(144, 145, text=now.strftime("%H:%M"), fill=bright, font=("Consolas", 36, "bold"))
        c.create_text(144, 184, text=now.strftime("%A  •  %d %B %Y").upper(),
                      fill="#56cce9", font=("Consolas", 10))
        panel(left, 294, 260, 488, "SYSTEM RESOURCES")
        stats = self._get_system_metrics()
        for i, (label, value) in enumerate(stats[:4]):
            yy = 338 + i*35
            c.create_text(48, yy, text=label, fill="#55aeca", anchor="w", font=("Consolas", 9))
            c.create_text(238, yy, text=value, fill=bright, anchor="e", font=("Consolas", 12, "bold"))
            c.create_rectangle(48, yy+12, 238, yy+18, outline="#075477")
            try:
                pct = float(value.rstrip("%"))
                c.create_rectangle(48, yy+12, 48+190*pct/100, yy+18, fill=blue, outline="")
            except Exception:
                pass
        panel(left, 504, 260, h-110, "QUICK ACCESS")
        quick = [("▣", "Documents"), ("▧", "Pictures"), ("♫", "Music"), ("⌁", "Downloads"), ("◉", "This PC")]
        for i, (symbol, label) in enumerate(quick):
            yy = 550 + i*42
            tag = "quick_" + label.lower().replace(" ", "_")
            c.create_text(52, yy, text=symbol, fill=blue, font=("Segoe UI", 15), tags=(tag,))
            c.create_text(78, yy, text=label, fill="#a8eaff", anchor="w", font=("Segoe UI", 10), tags=(tag,))
            c.tag_bind(tag, "<Button-1>", lambda _event, name=label: self.open_quick_access(name))
            c.tag_bind(tag, "<Enter>", lambda _event: c.configure(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda _event: c.configure(cursor=""))
            c.create_line(46, yy+18, 240, yy+18, fill="#092b3b")
        # Right-side system status and JARVIS info
        rx = w-270
        panel(rx, 88, w-28, 278, "ENVIRONMENT")
        metrics = dict(stats)
        c.create_text(rx+24, 145, text="CPU TEMPERATURE", fill="#55aeca", anchor="w", font=("Consolas", 9))
        c.create_text(w-92, 180, text=metrics.get("CPU TEMP", "N/A"), fill=bright, font=("Consolas", 27, "bold"))
        network_label = "NETWORK  •  ONLINE" if metrics.get("NETWORK") == "ONLINE" else "NETWORK  •  OFFLINE"
        c.create_text(rx+24, 220, text=network_label, fill="#62e8ff" if metrics.get("NETWORK") == "ONLINE" else "#ff8877", anchor="w", font=("Consolas", 9))
        panel(rx, 294, w-28, h-110, "J.A.R.V.I.S.  /  ASSISTANT")
        c.create_text(rx+24, 348, text="Always here for you.", fill=bright, anchor="w",
                      font=("Segoe UI", 14, "bold"))
        c.create_text(rx+24, 386, text="VOICE INTERFACE", fill="#55aeca", anchor="w", font=("Consolas", 9))
        c.create_text(rx+24, 422, text="Say  “Hey JARVIS”  to begin", fill="#b7eaff", anchor="w",
                      font=("Segoe UI", 10))
        c.create_text(rx+24, 478, text="CORE SERVICES", fill="#55aeca", anchor="w", font=("Consolas", 9))
        for i, (label, ready, detail) in enumerate(self._get_service_statuses()):
            yy = 512+i*35
            c.create_oval(rx+25, yy-5, rx+35, yy+5,
                          fill="#00e5a0" if ready else "#ffb454", outline="")
            c.create_text(rx+48, yy, text=label, fill="#a8eaff", anchor="w",
                          font=("Consolas", 9))
            c.create_text(w-45, yy, text=detail, fill="#65d9ef" if ready else "#ffb454",
                          anchor="e", font=("Consolas", 7))
        # Central reactor: concentric animated rings and radial energy arcs
        cx, cy = w/2, h*0.43
        radius = min(w*0.19, h*0.29, 245)
        for i in range(9, 0, -1):
            r = radius*(1+i*0.095)
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#06334b", width=1)
        for i in range(4):
            r = radius*(1.0+i*0.18)
            c.create_arc(cx-r, cy-r, cx+r, cy+r, start=self.orb_phase*(1 if i%2==0 else -1)+i*35,
                         extent=235, style="arc", outline=blue if i%2==0 else "#087ca8", width=3)
        for i in range(3):
            r = radius*(0.78-i*0.17)
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#087ca8", width=2)
        c.create_oval(cx-radius*.62, cy-radius*.62, cx+radius*.62, cy+radius*.62,
                      fill="#031b2c", outline=bright, width=3)
        c.create_oval(cx-radius*.48, cy-radius*.48, cx+radius*.48, cy+radius*.48,
                      outline=blue, width=2)
        for i in range(48):
            a = math.tau*i/48 + phase*.25
            r1, r2 = radius*.68, radius*.79
            c.create_line(cx+math.cos(a)*r1, cy+math.sin(a)*r1,
                          cx+math.cos(a)*r2, cy+math.sin(a)*r2,
                          fill=bright if i%4==0 else "#087ca8", width=2 if i%4==0 else 1)
        for i in range(80):
            a = i*2.399 + phase*(.2+(i%4)*.02)
            r = radius*(.18+((i*37)%100)/100*.76)
            x, y = cx+math.cos(a)*r, cy+math.sin(a)*r
            c.create_oval(x-1.5, y-1.5, x+1.5, y+1.5, fill=bright if i%5==0 else blue, outline="")
        c.create_oval(cx-radius*.18, cy-radius*.18, cx+radius*.18, cy+radius*.18,
                      fill="#06466a", outline=bright, width=2)
        c.create_oval(cx-radius*.09, cy-radius*.09, cx+radius*.09, cy+radius*.09,
                      fill="#9afaff", outline="#ffffff", width=2)
        c.create_text(cx, cy+radius+36, text="J A R V I S   /   REACTOR CORE",
                      fill=bright, font=("Consolas", 12, "bold"))
        # Labels and connector traces around reactor
        for label, x, y, side in [("IMAGES",cx-radius-165,cy-radius*.72,"left"),
                                  ("DOCUMENTS",cx-radius-165,cy-radius*.35,"left"),
                                  ("DOWNLOADS",cx-radius-165,cy+radius*.05,"left"),
                                  ("MUSIC",cx-radius-165,cy+radius*.45,"left"),
                                  ("GMAIL",cx+radius+65,cy-radius*.55,"right"),
                                  ("WHATSAPP",cx+radius+65,cy-radius*.18,"right"),
                                  ("DISCORD",cx+radius+65,cy+radius*.18,"right"),
                                  ("CHATGPT",cx+radius+65,cy+radius*.55,"right")]:
            c.create_oval(x-9, y-9, x+9, y+9, outline=blue, width=2)
            c.create_text(x+18, y, text=label, fill="#8deeff", anchor="w", font=("Consolas", 9))
            c.create_line(x+8, y+13, x+45, y+13, fill="#075477")
        # Bottom telemetry strip and live command bar
        by = h-84
        c.create_line(280, by-28, w-280, by-28, fill="#087ca8")
        c.create_text(300, by-10, text="SYSTEM STATUS  •  SECURE CONNECTION  •  ALL SYSTEMS NOMINAL",
                      fill="#58cbe8", anchor="w", font=("Consolas", 9))
        c.create_window(360, h-35, window=self.prompt_entry, width=max(350, w-780), height=34)
        c.create_window(w-190, h-35, window=self.send_button, width=120, height=34)
        c.create_window(w-330, h-35, window=self.stop_speaking_button, width=110, height=34)
        c.create_window(130, h-35, window=self.listen_button, width=190, height=34)
        c.create_text(w/2, h-91, text=self.status_var.get().upper(), fill=bright,
                      font=("Consolas", 9, "bold"))
        c.create_text(w-35, h-35, text="ESC  /  EXIT", fill="#328aa8", anchor="e",
                      font=("Consolas", 8))

    def _get_system_metrics(self):
        """Read actual Windows resource metrics, caching them between animation frames."""
        import time
        now = time.monotonic()
        cached = getattr(self, "_metrics_cache", None)
        if cached and now - cached[0] < 1.0:
            return cached[1]
        try:
            import psutil
            battery = psutil.sensors_battery()
            drive = os.environ.get("SystemDrive", "C:") + chr(92)
            disk = psutil.disk_usage(drive)
            try:
                temperatures = psutil.sensors_temperatures(fahrenheit=False)
                cpu_temp = next((entry.current for entries in temperatures.values()
                                 for entry in entries if entry.current is not None), None)
            except (AttributeError, NotImplementedError, OSError):
                cpu_temp = None
            network = any(info.isup for name, info in psutil.net_if_stats().items()
                          if name.lower() not in {"lo", "loopback"})
            values = [
                ("CPU LOAD", f"{psutil.cpu_percent(interval=None):.0f}%"),
                ("MEMORY", f"{psutil.virtual_memory().percent:.0f}%"),
                ("DISK USED", f"{disk.percent:.0f}%"),
                ("BATTERY", f"{battery.percent:.0f}%" if battery else "AC POWER"),
                ("CPU TEMP", f"{cpu_temp:.0f}°C" if cpu_temp is not None else "N/A"),
                ("NETWORK", "ONLINE" if network else "OFFLINE"),
            ]
        except Exception:
            values = [("CPU LOAD", "N/A"), ("MEMORY", "N/A"), ("DISK USED", "N/A"),
                      ("BATTERY", "N/A"), ("CPU TEMP", "N/A"), ("NETWORK", "OFFLINE")]
        self._metrics_cache = (now, values)
        return values

    def open_quick_access(self, name: str):
        """Open a real Windows known folder from the HUD shortcut."""
        import subprocess
        from pathlib import Path
        folders = {
            "Documents": Path.home() / "Documents",
            "Pictures": Path.home() / "Pictures",
            "Music": Path.home() / "Music",
            "Downloads": Path.home() / "Downloads",
            "This PC": Path(os.environ.get("SystemDrive", "C:") + "\\"),
        }
        target = folders[name]
        if not target.exists():
            messagebox.showwarning("Folder unavailable", f"{name} folder was not found.")
            return
        try:
            os.startfile(str(target))
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def open_chat(self):
        """Open a visible, scrollable conversation window."""
        if getattr(self, "chat_window", None) is not None and self.chat_window.winfo_exists():
            self.chat_window.deiconify()
            self.chat_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.chat_window = win
        win.title("JARVIS | Conversation")
        win.geometry("680x620")
        win.configure(bg="#03101b")
        win.minsize(480, 380)
        tk.Label(win, text="J.A.R.V.I.S.  /  LIVE CONVERSATION",
                 bg="#03101b", fg="#8af4ff", font=("Consolas", 13, "bold")).pack(
                     anchor="w", padx=16, pady=(14, 8))
        self.chat = tk.Text(win, state="disabled", bg="#041522", fg="#d9faff",
                            insertbackground="#ffffff", relief="flat",
                            font=("Segoe UI", 11), padx=12, pady=12, wrap="word")
        self.chat.pack(fill="both", expand=True, padx=14, pady=8)
        for who, content, tag in self.transcript:
            self.chat.configure(state="normal")
            self.chat.insert("end", who + "\n", "speaker")
            self.chat.insert("end", content + "\n\n", tag or "")
            self.chat.configure(state="disabled")
        self.chat.see("end")
        bottom = tk.Frame(win, bg="#03101b")
        bottom.pack(fill="x", padx=14, pady=(4, 14))
        ttk.Button(bottom, text="Clear conversation", style="HUD.TButton",
                   command=self.clear_chat).pack(side="left")
        ttk.Button(bottom, text="Close", style="HUD.TButton",
                   command=win.withdraw).pack(side="right")

    def _load_secrets(self):
        if self.keyring:
            try:
                self.api_key_var = tk.StringVar(value=self.keyring.get_password(KEYRING_SERVICE, "ai_api_key") or "")
                self.picovoice_var = tk.StringVar(value=self.keyring.get_password(KEYRING_SERVICE, "picovoice_access_key") or os.getenv("PICOVOICE_ACCESS_KEY", ""))
                return
            except Exception:
                pass
        self.api_key_var = tk.StringVar(value=os.getenv("JARVIS_AI_API_KEY", ""))
        self.picovoice_var = tk.StringVar(value=os.getenv("PICOVOICE_ACCESS_KEY", ""))

    def _append(self, who: str, text: str, tag: str | None = None):
        self.transcript.append((who, text, tag))
        if self.chat is None or not self.chat.winfo_exists():
            return
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}\n", "speaker")
        self.chat.insert("end", f"{text}\n\n", tag or "")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _try_local_command(self, prompt: str) -> bool:
        try:
            response = run_local_command(prompt)
        except Exception as exc:
            error_text = f"Could not run that approved action: {exc}"
            self._append("YOU", prompt)
            self._append("JARVIS ERROR", error_text, "error")
            self.history.extend([{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": error_text}])
            try:
                save_chat_history(self.history)
            except OSError:
                pass
            self._set_status("Local action failed.")
            return True
        if response is None:
            return False
        self._append("YOU", prompt)
        self.history.extend([{"role": "user", "content": prompt},
                             {"role": "assistant", "content": response}])
        try:
            save_chat_history(self.history)
        except OSError as exc:
            self._set_status(f"Action completed; chat history could not be saved: {exc}")
        self._append("JARVIS", response)
        self._set_status("Local action completed.")
        return True

    def send_text(self):
        prompt = self.prompt_var.get().strip()
        if not prompt or self.busy:
            return
        self.prompt_var.set("")
        if self._try_local_command(prompt):
            return
        if not self.request_lock.acquire(blocking=False):
            self.prompt_var.set(prompt)
            self._set_status("JARVIS is already answering; your message is ready to retry.")
            return
        self._append("YOU", prompt)
        self.busy = True
        self._set_status("Thinking…")
        try:
            threading.Thread(target=self._answer_worker, args=(prompt,), daemon=True).start()
        except Exception:
            self.busy = False
            self.request_lock.release()
            raise

    def _answer_worker(self, prompt: str):
        try:
            answer = chat_completion(
                self.settings.get("endpoint", DEFAULT_ENDPOINT),
                self.settings.get("model", DEFAULT_MODEL),
                self.ai_api_key,
                prompt,
                self.history,
            )
            self.history.extend([{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": answer}])
            try:
                save_chat_history(self.history)
            except OSError as exc:
                self.events.put(("status", f"Reply ready; chat history could not be saved: {exc}"))
            self.events.put(("answer", answer))
            try:
                self.speech_stop_event.clear()
                speak_text_interruptibly(answer, self.speech_stop_event)
            except Exception as exc:
                self.events.put(("status", f"Reply shown; speech output unavailable: {exc}"))
        except Exception as exc:
            # Keep failed prompts in local history so the conversation survives a restart.
            self.history.append({"role": "user", "content": prompt})
            try:
                save_chat_history(self.history)
            except OSError:
                pass
            self.events.put(("error", str(exc)))
        finally:
            self.request_lock.release()

    def stop_speaking(self):
        """Request speech cancellation; the TTS worker performs the engine stop safely."""
        self.speech_stop_event.set()
        self._set_status("Stopping spoken response…")

    def toggle_listening(self):
        if self.wake_thread and self.wake_thread.is_alive():
            self.stop_event.set()
            self.listen_button.configure(text="Stopping…", state="disabled")
            self._set_status("Stopping microphone listener…")
            return
        if not self.picovoice_access_key.strip():
            self.open_settings()
            self._set_status("Add a Picovoice AccessKey in Settings to enable wake listening.")
            return
        self.stop_event.clear()
        self.listen_button.configure(text="Stop wake listening")
        self._set_status("Starting local JARVIS wake-word detector…")
        self.wake_thread = threading.Thread(target=self._wake_loop, daemon=True)
        self.wake_thread.start()

    def _wake_loop(self):
        porcupine = None
        recorder = None
        try:
            import pvporcupine
            from pvrecorder import PvRecorder
            import speech_recognition as sr

            porcupine = pvporcupine.create(
                access_key=self.picovoice_access_key.strip(), 
                keywords=["jarvis"],
            )
            recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
            self.events.put(("status", "Listening locally for “Jarvis”. Windows may show its microphone indicator."))
            while not self.stop_event.is_set():
                recorder.start()
                try:
                    detected = False
                    while not self.stop_event.is_set():
                        if porcupine.process(recorder.read()) >= 0:
                            detected = True
                            break
                    recorder.stop()
                    if not detected or self.stop_event.is_set():
                        break
                    self.events.put(("status", "Wake word detected — speak your command now."))
                    recognizer = sr.Recognizer()
                    try:
                        with sr.Microphone() as source:
                            recognizer.adjust_for_ambient_noise(source, duration=0.35)
                            audio = recognizer.listen(source, timeout=5, phrase_time_limit=12)
                        command = recognizer.recognize_google(audio, language=self.settings.get("language", "en-IN"))
                        self.events.put(("status", f"Heard: {command}"))
                        self._answer_voice(command)
                    except sr.WaitTimeoutError:
                        self.events.put(("status", "No command heard. Listening again."))
                    except sr.UnknownValueError:
                        self.events.put(("status", "Sorry, I couldn't understand that. Listening again."))
                    except sr.RequestError as exc:
                        self.events.put(("status", f"Speech recognition needs internet; wake-word listening will continue: {exc}"))
                finally:
                    if recorder.is_recording:
                        recorder.stop()
        except Exception as exc:
            self.events.put(("error", f"Wake listener could not start: {exc}"))
        finally:
            if recorder is not None:
                try:
                    recorder.delete()
                except Exception:
                    pass
            if porcupine is not None:
                try:
                    porcupine.delete()
                except Exception:
                    pass
            self.events.put(("listener_stopped", None))

    def _answer_voice(self, prompt: str):
        self.events.put(("voice_command", prompt))
        try:
            local_response = run_local_command(prompt)
        except Exception as exc:
            self.events.put(("error", f"Could not run that approved action: {exc}"))
            return
        if local_response is not None:
            self.history.extend([{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": local_response}])
            try:
                save_chat_history(self.history)
            except OSError as exc:
                self.events.put(("status", f"Action completed; history could not be saved: {exc}"))
            self.events.put(("answer", local_response))
            self.events.put(("status", "Local action completed."))
            return
        if not self.request_lock.acquire(blocking=False):
            self.events.put(("status", "JARVIS is already answering; the voice request was skipped."))
            return
        try:
            answer = chat_completion(
                self.settings.get("endpoint", DEFAULT_ENDPOINT),
                self.settings.get("model", DEFAULT_MODEL),
                self.ai_api_key,
                prompt,
                self.history,
            )
            self.history.extend([{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": answer}])
            try:
                save_chat_history(self.history)
            except OSError as exc:
                self.events.put(("status", f"Reply ready; chat history could not be saved: {exc}"))
            self.events.put(("answer", answer))
            try:
                self.speech_stop_event.clear()
                speak_text_interruptibly(answer, self.speech_stop_event)
            except Exception as exc:
                self.events.put(("status", f"Reply shown; speech output unavailable: {exc}"))
        except Exception as exc:
            self.history.append({"role": "user", "content": prompt})
            try:
                save_chat_history(self.history)
            except OSError:
                pass
            self.events.put(("error", str(exc)))
        finally:
            self.request_lock.release()

    def open_power_controls(self):
        """Show explicit confirmation before scheduling a Windows power action."""
        window = tk.Toplevel(self.root)
        window.title("JARVIS | Power controls")
        window.configure(bg="#07111b")
        window.resizable(False, False)
        tk.Label(window, text="SYSTEM POWER CONTROLS", bg="#07111b", fg="#8af4ff",
                 font=("Consolas", 13, "bold")).pack(padx=20, pady=(18, 8))
        tk.Label(window, text="Shutdown and restart start a 60-second timer.\nYou can cancel it using the button below.",
                 bg="#07111b", fg="#d7f4ff", justify="center").pack(padx=20, pady=8)

        def request(action, title):
            if not messagebox.askyesno(
                title, f"Are you sure you want to {action} this PC?\n\n"
                       "The action will be scheduled for 60 seconds from now.",
                parent=window,
            ):
                return
            try:
                if not schedule_windows_power_action(action):
                    raise RuntimeError("Power controls are available only on Windows.")
                self._set_status(f"{title} scheduled. You have 60 seconds to cancel.")
                messagebox.showinfo("JARVIS", f"{title} scheduled. Use Cancel pending action within 60 seconds.",
                                    parent=window)
            except Exception as exc:
                messagebox.showerror("Power action failed", str(exc), parent=window)

        ttk.Button(window, text="Shut down (60 sec)", style="HUD.TButton",
                   command=lambda: request("shut down", "Shutdown")).pack(fill="x", padx=24, pady=5)
        ttk.Button(window, text="Restart (60 sec)", style="HUD.TButton",
                   command=lambda: request("restart", "Restart")).pack(fill="x", padx=24, pady=5)
        ttk.Button(window, text="Cancel pending shutdown/restart", style="HUD.TButton",
                   command=lambda: self._cancel_power_action(window)).pack(fill="x", padx=24, pady=5)
        ttk.Button(window, text="Close", style="HUD.TButton",
                   command=window.destroy).pack(padx=24, pady=(8, 18))

    def _cancel_power_action(self, parent):
        try:
            if not schedule_windows_power_action("cancel"):
                raise RuntimeError("Power controls are available only on Windows.")
            self._set_status("Pending shutdown/restart cancellation requested.")
            messagebox.showinfo("JARVIS", "Cancellation command sent.", parent=parent)
        except Exception as exc:
            messagebox.showerror("Could not cancel", str(exc), parent=parent)

    def open_settings(self):
        window = tk.Toplevel(self.root)
        window.title("JARVIS Settings")
        window.configure(bg="#07111b")
        window.resizable(False, False)
        fields = [
            ("AI endpoint (HTTPS)", "endpoint", self.settings.get("endpoint", DEFAULT_ENDPOINT)),
            ("Model", "model", self.settings.get("model", DEFAULT_MODEL)),
            ("JARVIS backend client token (not OpenRouter key)", "ai_key", self.api_key_var.get()),
            ("Picovoice AccessKey", "picovoice_key", self.picovoice_var.get()),
        ]
        entries = {}
        for row, (label, name, value) in enumerate(fields):
            tk.Label(window, text=label, bg="#07111b", fg="#d7f4ff",
                     font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=14, pady=8)
            entry = ttk.Entry(window, width=58, show="*" if name.endswith("key") else "")
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=14, pady=8)
            entries[name] = entry
        tk.Label(window, text="Speech recognition language", bg="#07111b", fg="#d7f4ff",
                 font=("Segoe UI", 10)).grid(row=4, column=0, sticky="w", padx=14, pady=8)
        language = ttk.Combobox(window, values=["en-IN", "hi-IN", "en-US"], state="readonly", width=12)
        language.set(self.settings.get("language", "en-IN"))
        language.grid(row=4, column=1, sticky="w", padx=14, pady=8)
        startup_var = tk.BooleanVar(value=bool(self.settings.get("start_with_windows", False)))
        ttk.Checkbutton(window, text="Start JARVIS when I sign in to Windows",
                        variable=startup_var).grid(row=5, column=1, sticky="w", padx=14, pady=8)
        tk.Label(window, text="Closing the window keeps JARVIS in the system tray. Use Exit from its tray menu.",
                 bg="#07111b", fg="#7897aa", font=("Segoe UI", 9)).grid(
                     row=6, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 4))
        tk.Label(window, text="Secrets are stored in Windows Credential Manager when available.",
                 bg="#07111b", fg="#7897aa", font=("Segoe UI", 9)).grid(
                     row=7, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 12))

        def save():
            self.settings["endpoint"] = entries["endpoint"].get().strip()
            self.settings["model"] = entries["model"].get().strip()
            self.settings["language"] = language.get().strip() or "en-IN"
            startup_enabled = startup_var.get()
            try:
                set_windows_startup(startup_enabled)
            except Exception as exc:
                messagebox.showerror("Startup setting failed", str(exc), parent=window)
                return
            self.settings["start_with_windows"] = startup_enabled
            self.api_key_var.set(entries["ai_key"].get().strip())
            self.picovoice_var.set(entries["picovoice_key"].get().strip())
            self.ai_api_key = self.api_key_var.get()
            self.picovoice_access_key = self.picovoice_var.get()
            try:
                save_settings(self.settings)
                if self.keyring:
                    self.keyring.set_password(KEYRING_SERVICE, "ai_api_key", self.api_key_var.get())
                    self.keyring.set_password(KEYRING_SERVICE, "picovoice_access_key", self.picovoice_var.get())
                elif self.api_key_var.get() or self.picovoice_var.get():
                    messagebox.showwarning(
                        "Secure storage unavailable",
                        "Windows Credential Manager could not be accessed. Keys will only remain in memory for this session.",
                        parent=window,
                    )
            except Exception as exc:
                messagebox.showerror("Could not save", str(exc), parent=window)
                return
            self._set_status("Settings saved.")
            window.destroy()

        ttk.Button(window, text="Save settings", command=save).grid(
            row=8, column=1, sticky="e", padx=14, pady=(4, 16))

    def clear_chat(self):
        self.history.clear()
        self.transcript.clear()
        try:
            save_chat_history(self.history)
        except OSError as exc:
            self._set_status(f"Chat cleared in memory; could not update history file: {exc}")
        if self.chat is not None and self.chat.winfo_exists():
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.configure(state="disabled")
        self._append("JARVIS", "Conversation cleared.")

    def _poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "answer":
                    self._append("JARVIS", value)
                    self.busy = False
                    self._set_status("Ready.")
                elif kind == "error":
                    self._append("JARVIS ERROR", value, "error")
                    self.busy = False
                    self._set_status("Something needs attention.")
                elif kind == "status":
                    self._set_status(value)
                elif kind == "voice_command":
                    self._append("YOU (VOICE)", value)
                elif kind == "listener_stopped":
                    self.listen_button.configure(text="Start wake listening", state="normal")
                    self._set_status("Wake listener stopped.")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _show_window(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _start_tray(self):
        if self.tray_icon is not None:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw

            image = Image.new("RGBA", (64, 64), (2, 7, 13, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((5, 5, 59, 59), outline=(0, 191, 255, 255), width=3)
            draw.ellipse((15, 15, 49, 49), outline=(138, 244, 255, 255), width=2)
            draw.ellipse((27, 27, 37, 37), fill=(0, 191, 255, 255))
            menu = pystray.Menu(
                pystray.MenuItem("Open JARVIS", lambda _icon, _item: self._show_window(), default=True),
                pystray.MenuItem("Activate / stop voice", lambda _icon, _item: self.root.after(0, self.toggle_listening)),
                pystray.MenuItem("Stop speaking", lambda _icon, _item: self.root.after(0, self.stop_speaking)),
                pystray.MenuItem("Exit JARVIS", lambda _icon, _item: self.root.after(0, self.exit_app)),
            )
            self.tray_icon = pystray.Icon(APP_NAME, image, "JARVIS Desktop", menu)
            self.tray_icon.run_detached()
            return True
        except Exception as exc:
            self.tray_icon = None
            self._set_status(f"System tray unavailable: {exc}")
            return False

    def hide_to_tray(self):
        if self._start_tray():
            self.root.withdraw()
            self._set_status("JARVIS is running in the system tray.")
            return
        if messagebox.askyesno(
            "JARVIS system tray unavailable",
            "The tray component could not start. Exit JARVIS instead?",
            parent=self.root,
        ):
            self.exit_app()

    def exit_app(self):
        self.stop_event.set()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.root.destroy()

    def close(self):
        """Backward-compatible explicit exit hook."""
        self.exit_app()


def main():
    root = tk.Tk()
    JarvisDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
