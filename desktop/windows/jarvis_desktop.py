"""Native Windows companion app for JARVIS.

Keys are stored in Windows Credential Manager via keyring, never in the settings JSON.
"""
from __future__ import annotations

import json
import os
import queue
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
        self.history: list[dict] = []
        self.stop_event = threading.Event()
        self.wake_thread: threading.Thread | None = None
        self.busy = False
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
        self.root.protocol("WM_DELETE_WINDOW", self.close)

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
        self.prompt_var = tk.StringVar()
        self.prompt_entry = ttk.Entry(self.root, textvariable=self.prompt_var, style="HUD.TEntry")
        self.send_button = ttk.Button(self.root, text="TRANSMIT  ➤", style="HUD.TButton", command=self.send_text)
        self.listen_button = ttk.Button(self.root, text="◉  ACTIVATE VOICE", style="HUD.TButton",
                                        command=self.toggle_listening)
        self._draw_orb()
        self.root.after(50, self._animate_orb)

    def _animate_orb(self):
        if not self.root.winfo_exists():
            return
        self.orb_phase = (self.orb_phase + 1.2) % 360.0
        self._draw_orb()
        self.root.after(55, self._animate_orb)

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
        c.create_oval(w-190, 25, w-178, 37, fill="#00f0a0", outline="")
        c.create_text(w-165, 31, text="SYSTEM ONLINE", fill=bright, anchor="w",
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
        stats = []
        try:
            import psutil
            stats = [("CPU LOAD", f"{psutil.cpu_percent():.0f}%"),
                     ("MEMORY", f"{psutil.virtual_memory().percent:.0f}%"),
                     ("BATTERY", f"{psutil.sensors_battery().percent:.0f}%" if psutil.sensors_battery() else "AC POWER")]
        except Exception:
            stats = [("CPU LOAD", "N/A"), ("MEMORY", "N/A"), ("BATTERY", "N/A")]
        for i, (label, value) in enumerate(stats):
            yy = 340 + i*45
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
            c.create_text(52, yy, text=symbol, fill=blue, font=("Segoe UI", 15))
            c.create_text(78, yy, text=label, fill="#a8eaff", anchor="w", font=("Segoe UI", 10))
            c.create_line(46, yy+18, 240, yy+18, fill="#092b3b")
        # Right-side system status and JARVIS info
        rx = w-270
        panel(rx, 88, w-28, 278, "ENVIRONMENT")
        c.create_text(rx+24, 145, text="CPU TEMPERATURE", fill="#55aeca", anchor="w", font=("Consolas", 9))
        c.create_text(w-92, 180, text="--°C", fill=bright, font=("Consolas", 27, "bold"))
        c.create_text(rx+24, 220, text="NETWORK  •  CONNECTED", fill="#62e8ff", anchor="w", font=("Consolas", 9))
        panel(rx, 294, w-28, h-110, "J.A.R.V.I.S.  /  ASSISTANT")
        c.create_text(rx+24, 348, text="Always here for you.", fill=bright, anchor="w",
                      font=("Segoe UI", 14, "bold"))
        c.create_text(rx+24, 386, text="VOICE INTERFACE", fill="#55aeca", anchor="w", font=("Consolas", 9))
        c.create_text(rx+24, 422, text="Say  “Hey JARVIS”  to begin", fill="#b7eaff", anchor="w",
                      font=("Segoe UI", 10))
        c.create_text(rx+24, 478, text="CORE SERVICES", fill="#55aeca", anchor="w", font=("Consolas", 9))
        for i, label in enumerate(("AI CHAT", "VOICE ENGINE", "MEMORY", "SYSTEM CONTROL")):
            yy = 512+i*35
            c.create_oval(rx+25, yy-5, rx+35, yy+5, fill="#00e5a0", outline="")
            c.create_text(rx+48, yy, text=label, fill="#a8eaff", anchor="w", font=("Consolas", 9))
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
        c.create_window(130, h-35, window=self.listen_button, width=190, height=34)
        c.create_text(w/2, h-91, text=self.status_var.get().upper(), fill=bright,
                      font=("Consolas", 9, "bold"))
        c.create_text(w-35, h-35, text="ESC  /  EXIT", fill="#328aa8", anchor="e",
                      font=("Consolas", 8))

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
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}\n", "speaker")
        self.chat.insert("end", f"{text}\n\n", tag or "")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _set_status(self, text: str):
        self.status_var.set(text)

    def send_text(self):
        prompt = self.prompt_var.get().strip()
        if not prompt or self.busy:
            return
        if not self.request_lock.acquire(blocking=False):
            self._set_status("JARVIS is already answering; please wait.")
            return
        self.prompt_var.set("")
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
            self.events.put(("answer", answer))
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(answer)
                engine.runAndWait()
                engine.stop()
            except Exception as exc:
                self.events.put(("status", f"Reply shown; speech output unavailable: {exc}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.request_lock.release()

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
                        self.events.put(("voice_command", command))
                        self.events.put(("status", f"Heard: {command}"))
                        self._answer_voice(command)
                    except sr.WaitTimeoutError:
                        self.events.put(("status", "No command heard. Listening again."))
                    except sr.UnknownValueError:
                        self.events.put(("status", "Sorry, I couldn't understand that. Listening again."))
                    except sr.RequestError as exc:
                        self.events.put(("error", f"Speech recognition needs internet: {exc}"))
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
            self.events.put(("answer", answer))
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(answer)
                engine.runAndWait()
                engine.stop()
            except Exception as exc:
                self.events.put(("status", f"Reply shown; speech output unavailable: {exc}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.request_lock.release()

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
        tk.Label(window, text="Secrets are stored in Windows Credential Manager when available.",
                 bg="#07111b", fg="#7897aa", font=("Segoe UI", 9)).grid(
                     row=5, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 12))

        def save():
            self.settings["endpoint"] = entries["endpoint"].get().strip()
            self.settings["model"] = entries["model"].get().strip()
            self.settings["language"] = language.get().strip() or "en-IN"
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
            row=6, column=1, sticky="e", padx=14, pady=(4, 16))

    def clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.history.clear()
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

    def close(self):
        self.stop_event.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    JarvisDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
