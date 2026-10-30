"""Optional local Vosk speech recognition and safe model installation for JARVIS."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MODEL_CATALOG = {
    "hi-IN": (
        "vosk-model-small-hi-0.22",
        "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip",
    ),
    "en-IN": (
        "vosk-model-small-en-in-0.4",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip",
    ),
    "en-US": (
        "vosk-model-small-en-us-0.15",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    ),
}
DEFAULT_MODEL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JARVISDesktop" / "models"


class OfflineModelUnavailable(RuntimeError):
    """Raised when the selected offline speech model has not been installed."""


def model_path_for_language(language: str, model_dir: Path = DEFAULT_MODEL_DIR) -> Path:
    try:
        model_name, _url = MODEL_CATALOG[language]
    except KeyError as exc:
        raise ValueError("Unsupported offline speech language.") from exc
    return Path(model_dir) / model_name


def transcribe_offline_vosk(audio, language: str, model_dir: Path = DEFAULT_MODEL_DIR,
                            vosk_module=None) -> str:
    """Transcribe SpeechRecognition AudioData locally; no network access is used."""
    model_path = model_path_for_language(language, model_dir)
    if not model_path.is_dir():
        raise OfflineModelUnavailable(
            f"Offline {language} model is missing. Install it from JARVIS Settings while online."
        )
    if vosk_module is None:
        try:
            import vosk as vosk_module
        except ImportError as exc:
            raise OfflineModelUnavailable("Install the Vosk speech package to enable offline voice.") from exc
    raw_audio = audio.get_raw_data(convert_rate=16000, convert_width=2)
    model = vosk_module.Model(str(model_path))
    recognizer = vosk_module.KaldiRecognizer(model, 16000)
    recognizer.AcceptWaveform(raw_audio)
    result = json.loads(recognizer.FinalResult())
    text = result.get("text", "") if isinstance(result, dict) else ""
    return text.strip()


def install_offline_model(language: str, model_dir: Path = DEFAULT_MODEL_DIR,
                          urlopen=urllib.request.urlopen) -> Path:
    """Download and safely extract one official, small Vosk model for later offline use."""
    try:
        model_name, url = MODEL_CATALOG[language]
    except KeyError as exc:
        raise ValueError("Unsupported offline speech language.") from exc
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    destination = model_dir / model_name
    if destination.is_dir():
        return destination

    staging = Path(tempfile.mkdtemp(prefix="jarvis-vosk-", dir=str(model_dir)))
    archive_path = staging / "model.zip"
    extracted = staging / "extracted"
    extracted.mkdir()
    try:
        with urlopen(url, timeout=30) as response, archive_path.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 250 * 1024 * 1024:
                    raise RuntimeError("The offline model download exceeded the 250 MB safety limit.")
                output.write(chunk)
        with zipfile.ZipFile(archive_path) as archive:
            root = extracted.resolve()
            for member in archive.infolist():
                target = (extracted / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError("The model archive contains an unsafe file path.")
            archive.extractall(extracted)
        source = extracted / model_name
        if not source.is_dir() or not any(source.iterdir()):
            raise RuntimeError("The downloaded speech model archive is incomplete.")
        source.rename(destination)
        return destination
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(f"Could not install the offline speech model: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
