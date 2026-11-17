"""One-shot, local-only spoken approval for sensitive JARVIS actions."""
from __future__ import annotations

import re
import secrets
import threading
import tkinter as tk
from tkinter import ttk


_CHALLENGE_WORDS = (
    "amber", "cobalt", "falcon", "harbor", "maple",
    "orbit", "silver", "tiger", "violet", "willow",
)


def normalize_spoken_text(value: str) -> str:
    """Normalize ASR output without accepting extra words or fuzzy matches."""
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def parse_voice_approval(transcript: str, challenge: str) -> bool | None:
    """Return True/False only for the exact one-time spoken phrase; otherwise fail closed."""
    heard = normalize_spoken_text(transcript)
    if heard == normalize_spoken_text(f"jarvis approve {challenge}"):
        return True
    if heard == normalize_spoken_text(f"jarvis deny {challenge}"):
        return False
    return None


def request_voice_permission(
    parent,
    spoken_summary: str,
    *,
    language: str = "en-IN",
    recognizer_factory=None,
    microphone_factory=None,
    transcriber=None,
    speech_factory=None,
    challenge_factory=None,
) -> bool:
    """Speak the exact action, then accept one local Vosk approval/denial phrase.

    No cloud speech API is used. Missing microphone consent, models, unclear speech,
    timeout, dialog close, and all errors deny the action.
    """
    challenge = (challenge_factory or secrets.choice)(_CHALLENGE_WORDS)
    approve_phrase = f"JARVIS approve {challenge}"
    deny_phrase = f"JARVIS deny {challenge}"

    dialog = tk.Toplevel(parent)
    dialog.title("JARVIS — Voice permission")
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.grab_set()
    status = tk.StringVar(value="JARVIS is speaking the action details…")
    ttk.Label(
        dialog,
        text="Sensitive action permission",
        font=("Segoe UI", 12, "bold"),
    ).pack(padx=22, pady=(18, 8), anchor="w")
    ttk.Label(
        dialog,
        text=spoken_summary,
        wraplength=520,
        justify="left",
    ).pack(padx=22, pady=6, anchor="w")
    ttk.Label(
        dialog,
        textvariable=status,
        wraplength=520,
        justify="left",
    ).pack(padx=22, pady=(8, 18), anchor="w")

    finished = threading.Event()
    cancelled = threading.Event()
    decision = {"approved": False}

    def finish(approved: bool, message: str):
        if finished.is_set():
            return
        decision["approved"] = bool(approved)
        status.set(message)
        finished.set()
        try:
            dialog.grab_release()
            dialog.destroy()
        except tk.TclError:
            pass

    def close_dialog():
        cancelled.set()
        finish(False, "Permission cancelled. No action was performed.")

    dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    def worker():
        try:
            if speech_factory is None:
                import pyttsx3
                engine = pyttsx3.init()
            else:
                engine = speech_factory()
            try:
                engine.say(
                    f"JARVIS needs your permission. {spoken_summary}. "
                    f"To approve, say {approve_phrase}. "
                    f"To deny, say {deny_phrase}."
                )
                engine.runAndWait()
            finally:
                try:
                    engine.stop()
                except Exception:
                    pass

            if cancelled.is_set():
                return

            if recognizer_factory is None or microphone_factory is None:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                microphone = sr.Microphone
            else:
                recognizer = recognizer_factory()
                microphone = microphone_factory

            with microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.35)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=6)

            if cancelled.is_set():
                return

            if transcriber is None:
                from offline_speech import transcribe_offline_vosk
                transcript = transcribe_offline_vosk(audio, language)
            else:
                transcript = transcriber(audio, language)

            parsed = parse_voice_approval(transcript, challenge)
            if parsed is True:
                message = "Voice approval received. This exact action is approved once."
                approved = True
            elif parsed is False:
                message = "Voice denial received. No action was performed."
                approved = False
            else:
                message = "Voice response did not match. Permission denied; no action was performed."
                approved = False
        except Exception as exc:
            approved = False
            message = f"Voice permission unavailable or unclear: {exc}. No action was performed."

        def complete():
            if not cancelled.is_set():
                finish(approved, message)
        try:
            parent.after(0, complete)
        except tk.TclError:
            pass

    threading.Thread(target=worker, name="JARVIS-voice-permission", daemon=True).start()
    parent.wait_window(dialog)
    return bool(decision["approved"])
