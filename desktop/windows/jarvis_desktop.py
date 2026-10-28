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
DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    'You are J.A.R.V.I.S., a calm, polished personal AI butler with subtle dry wit. '
    'Support Hindi, English, and Hinglish. Match the language and script used by the user. '
    'Be concise when the reply will be spoken aloud. Never claim an action succeeded unless it did.'
)


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL, "language": "en-IN"}


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

        try:
            import keyring
            self.keyring = keyring
        except Exception:
            self.keyring = None

        self._build_ui()
        self._load_secrets()
        self.root.after(120, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=8, font=("Segoe UI", 10))
        style.configure("TLabel", background="#07111b", foreground="#d7f4ff", font=("Segoe UI", 10))
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)

        header = tk.Frame(self.root, bg="#07111b")
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(header, text="J.A.R.V.I.S.", bg="#07111b", fg="#5de2e7",
                 font=("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(header, text="DESKTOP ASSISTANT  •  WINDOWS 11", bg="#07111b", fg="#7897aa",
                 font=("Consolas", 9)).pack(anchor="w", pady=(2, 0))

        self.status_var = tk.StringVar(value="Ready — configure your AI key and Picovoice key below.")
        tk.Label(self.root, textvariable=self.status_var, bg="#0c1d2b", fg="#8ce9ed",
                 anchor="w", padx=14, pady=10).pack(fill="x", padx=24, pady=(8, 12))

        self.chat = tk.Text(self.root, bg="#0b1925", fg="#e4f4ff", insertbackground="#e4f4ff",
                            relief="flat", wrap="word", padx=14, pady=12,
                            font=("Segoe UI", 11), state="disabled")
        self.chat.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self.chat.tag_configure("speaker", foreground="#5de2e7", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("error", foreground="#ff9d9d")

        entry_row = tk.Frame(self.root, bg="#07111b")
        entry_row.pack(fill="x", padx=24, pady=(0, 12))
        self.prompt_var = tk.StringVar()
        self.prompt_entry = ttk.Entry(entry_row, textvariable=self.prompt_var)
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.prompt_entry.bind("<Return>", lambda _event: self.send_text())
        ttk.Button(entry_row, text="Send", command=self.send_text).pack(side="right")

        controls = tk.Frame(self.root, bg="#07111b")
        controls.pack(fill="x", padx=24, pady=(0, 20))
        self.listen_button = ttk.Button(controls, text="Start wake listening", command=self.toggle_listening)
        self.listen_button.pack(side="left")
        ttk.Button(controls, text="Settings", command=self.open_settings).pack(side="left", padx=8)
        ttk.Button(controls, text="Clear chat", command=self.clear_chat).pack(side="right")
        self._append("JARVIS", "Ready when you are. Type a message or configure wake-word listening in Settings.")

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
        self.prompt_var.set("")
        self._append("YOU", prompt)
        self.busy = True
        self._set_status("Thinking…")
        threading.Thread(target=self._answer_worker, args=(prompt,), daemon=True).start()

    def _answer_worker(self, prompt: str):
        try:
            answer = chat_completion(
                self.settings.get("endpoint", DEFAULT_ENDPOINT),
                self.settings.get("model", DEFAULT_MODEL),
                self.api_key_var.get(),
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

    def toggle_listening(self):
        if self.wake_thread and self.wake_thread.is_alive():
            self.stop_event.set()
            self.listen_button.configure(text="Stopping…", state="disabled")
            self._set_status("Stopping microphone listener…")
            return
        if not self.picovoice_var.get().strip():
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
                access_key=self.picovoice_var.get().strip(),
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
        try:
            answer = chat_completion(
                self.settings.get("endpoint", DEFAULT_ENDPOINT),
                self.settings.get("model", DEFAULT_MODEL),
                self.api_key_var.get(),
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

    def open_settings(self):
        window = tk.Toplevel(self.root)
        window.title("JARVIS Settings")
        window.configure(bg="#07111b")
        window.resizable(False, False)
        fields = [
            ("AI endpoint (HTTPS)", "endpoint", self.settings.get("endpoint", DEFAULT_ENDPOINT)),
            ("Model", "model", self.settings.get("model", DEFAULT_MODEL)),
            ("AI API key", "ai_key", self.api_key_var.get()),
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
