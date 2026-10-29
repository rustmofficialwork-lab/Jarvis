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
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=8, font=("Segoe UI", 10))
        style.configure("TLabel", background="#050505", foreground="#f2d1b2", font=("Segoe UI", 10))
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)

        self.root.configure(bg="#050505")
        header = tk.Frame(self.root, bg="#050505")
        header.pack(fill="x", padx=24, pady=(12, 2))
        tk.Label(header, text="J.A.R.V.I.S.", bg="#050505", fg="#ff8a18",
                 font=("Segoe UI Semibold", 21)).pack(anchor="center")
        tk.Label(header, text="PERSONAL AI • DESKTOP INTERFACE", bg="#050505", fg="#80502e",
                 font=("Consolas", 9)).pack(anchor="center", pady=(1, 0))

        # Large animated canvas: particle sphere and flowing energy ribbons, matching the chosen orange orb.
        self.orb_canvas = tk.Canvas(self.root, bg="#000000", highlightthickness=0, height=290)
        self.orb_canvas.pack(fill="both", expand=True, padx=18, pady=(4, 2))
        self.orb_phase = 0.0
        self.orb_canvas.bind("<Configure>", lambda _event: self._draw_orb())

        self.status_var = tk.StringVar(value="Ready — configure your AI endpoint and client token in Settings.")
        tk.Label(self.root, textvariable=self.status_var, bg="#100a06", fg="#ffb36b",
                 anchor="center", padx=12, pady=8).pack(fill="x", padx=24, pady=(4, 8))

        self.chat = tk.Text(self.root, bg="#0b0908", fg="#f5e7db", insertbackground="#f5e7db",
                            relief="flat", wrap="word", padx=12, pady=8,
                            font=("Segoe UI", 10), height=5, state="disabled")
        self.chat.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self.chat.tag_configure("speaker", foreground="#ff9a3d", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("error", foreground="#ff9d9d")

        entry_row = tk.Frame(self.root, bg="#050505")
        entry_row.pack(fill="x", padx=24, pady=(0, 8))
        self.prompt_var = tk.StringVar()
        self.prompt_entry = ttk.Entry(entry_row, textvariable=self.prompt_var)
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.prompt_entry.bind("<Return>", lambda _event: self.send_text())
        ttk.Button(entry_row, text="Send", command=self.send_text).pack(side="right")

        controls = tk.Frame(self.root, bg="#050505")
        controls.pack(fill="x", padx=24, pady=(0, 12))
        self.listen_button = ttk.Button(controls, text="Start wake listening", command=self.toggle_listening)
        self.listen_button.pack(side="left")
        ttk.Button(controls, text="Settings", command=self.open_settings).pack(side="left", padx=8)
        ttk.Button(controls, text="Clear chat", command=self.clear_chat).pack(side="right")
        self._append("JARVIS", "Ready when you are. Type a message or configure wake-word listening in Settings.")
        self._draw_orb()
        self.root.after(50, self._animate_orb)

    def _animate_orb(self):
        if not self.root.winfo_exists():
            return
        # Smooth, continuous motion without redrawing thousands of expensive objects.
        self.orb_phase = (self.orb_phase + 1.6) % 360.0
        self._draw_orb()
        self.root.after(40, self._animate_orb)

    def _draw_orb(self):
        if not hasattr(self, "orb_canvas"):
            return
        import math
        canvas = self.orb_canvas
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 220)
        canvas.delete("all")
        cx, cy = width / 2.0, height / 2.0
        phase = math.radians(self.orb_phase)
        pulse = 1.0 + 0.018 * math.sin(phase * 1.7)
        radius = min(width * 0.245, height * 0.405, 225) * pulse

        # Deep black background with a layered amber aura around the orb.
        for ring in range(18, 0, -1):
            r = radius * (0.58 + ring * 0.045)
            shade = max(0, 30 - ring)
            color = f"#{shade:02x}{max(0, shade//3):02x}00"
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")

        # Sparse drifting embers around the sphere.
        for i in range(86):
            angle = i * 2.399963 + phase * (0.12 + (i % 5) * 0.025)
            distance = radius * (1.08 + ((i * 43) % 100) / 100 * 0.58)
            sx = cx + math.cos(angle) * distance
            sy = cy + math.sin(angle) * distance * 0.88
            twinkle = (i + int(self.orb_phase * 2)) % 7
            if twinkle in (0, 1):
                size = 1.2 if i % 3 else 2.0
                canvas.create_oval(sx-size, sy-size, sx+size, sy+size,
                                   fill="#ff6a08" if twinkle else "#ffb34d", outline="")

        # Dense, rotating particle shell. Keep the centre dark like the selected reference.
        colors = ["#ff3b00", "#ff5100", "#ff6a00", "#ff8b12", "#ffb33c", "#ffe0a0"]
        for i in range(820):
            angle = i * 2.3999632297 + phase * (0.20 + (i % 11) * 0.009)
            spread = math.sqrt(((i * 97) % 823) / 823.0)
            wobble = 0.94 + 0.045 * math.sin(angle * 3.0 + phase * 1.3)
            px = cx + math.cos(angle) * radius * spread * wobble
            py = cy + math.sin(angle) * radius * spread * wobble
            core = ((px-cx)/(radius*0.67))**2 + ((py-cy)/(radius*0.67))**2
            if core < 0.92 and i % 7 != 0:
                continue
            color = colors[(i * 13 + int(self.orb_phase * 0.6)) % len(colors)]
            dot = 0.8 if i % 5 else 1.7
            canvas.create_oval(px-dot, py-dot, px+dot, py+dot, fill=color, outline="")

        # Multiple luminous curved energy ribbons rotate around the particle shell.
        ribbons = [
            (0.94, 0.60, 218 + self.orb_phase * 0.58, 232, "#ffb84f", 2),
            (0.87, 0.47, 24 - self.orb_phase * 0.43, 248, "#ff6a0a", 2),
            (0.68, 0.84, 122 + self.orb_phase * 0.31, 218, "#ff8a19", 1),
            (0.98, 0.72, 305 - self.orb_phase * 0.24, 110, "#ff4a00", 1),
        ]
        for rx, ry, start, extent, color, line_width in ribbons:
            xrad, yrad = radius * rx, radius * ry
            canvas.create_arc(cx-xrad, cy-yrad, cx+xrad, cy+yrad,
                              start=start, extent=extent, style="arc",
                              outline=color, width=line_width)

        # Fine bright rim and small moving highlights make the sphere feel energized.
        canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                           outline="#ff8a20", width=1)
        for j in range(7):
            a = phase * 1.25 + j * (math.tau / 7)
            hx = cx + math.cos(a) * radius * 0.985
            hy = cy + math.sin(a) * radius * 0.985
            canvas.create_oval(hx-2, hy-2, hx+2, hy+2,
                               fill="#ffe2a0", outline="#ff6a00")
        # A subtle warm core glint; most of the centre remains dark.
        core_r = radius * (0.025 + 0.004 * math.sin(phase * 2))
        canvas.create_oval(cx-core_r, cy-core_r, cx+core_r, cy+core_r,
                           fill="#ff9a25", outline="#ffe1a0", width=1)

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
