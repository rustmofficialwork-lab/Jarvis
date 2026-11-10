"""Optional local Vosk speech recognition and safe model installation for JARVIS."""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import threading
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
MAX_MODEL_DOWNLOAD_BYTES = 250 * 1024 * 1024
MAX_MODEL_EXTRACTED_BYTES = 500 * 1024 * 1024
MAX_MODEL_ARCHIVE_ENTRIES = 20000
ALLOWED_MODEL_HOSTS = {"alphacephei.com", "www.alphacephei.com"}


def _is_allowed_model_redirect_url(value: str) -> bool:
    """Keep model downloads on the official HTTPS model host."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(value)
        valid_port = parsed.port is None or parsed.port == 443
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_MODEL_HOSTS
        and not parsed.username
        and not parsed.password
        and valid_port
    )


class OfflineModelUnavailable(RuntimeError):
    """Raised when the selected offline speech model has not been installed."""


_VOSK_MODEL_CACHE_LOCK = threading.Lock()
_VOSK_MODEL_CACHE = None


def _get_cached_vosk_model(model_path: Path, vosk_module):
    """Reuse one loaded local model so fallback transcription avoids repeated disk loads."""
    global _VOSK_MODEL_CACHE
    cache_key = str(model_path.resolve())
    with _VOSK_MODEL_CACHE_LOCK:
        if (_VOSK_MODEL_CACHE is not None
                and _VOSK_MODEL_CACHE[0] == cache_key
                and _VOSK_MODEL_CACHE[1] is vosk_module):
            return _VOSK_MODEL_CACHE[2]
        model = vosk_module.Model(str(model_path))
        # Keep only one language model resident to bound JARVIS memory usage.
        _VOSK_MODEL_CACHE = (cache_key, vosk_module, model)
        return model


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
            f"Offline {language} model is missing. JARVIS will download it automatically when an internet connection is available."
        )
    if vosk_module is None:
        try:
            import vosk as vosk_module
        except ImportError as exc:
            raise OfflineModelUnavailable("Install the Vosk speech package to enable offline voice.") from exc
    raw_audio = audio.get_raw_data(convert_rate=16000, convert_width=2)
    model = _get_cached_vosk_model(model_path, vosk_module)
    recognizer = vosk_module.KaldiRecognizer(model, 16000)
    recognizer.AcceptWaveform(raw_audio)
    result = json.loads(recognizer.FinalResult())
    text = result.get("text", "") if isinstance(result, dict) else ""
    return text.strip()


def install_offline_model(language: str, model_dir: Path = DEFAULT_MODEL_DIR,
                          urlopen=None) -> Path:
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

    if urlopen is None:
        class SafeModelRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not _is_allowed_model_redirect_url(newurl):
                    return None
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(SafeModelRedirect)
        urlopen = opener.open

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
                if total > MAX_MODEL_DOWNLOAD_BYTES:
                    raise RuntimeError("The offline model download exceeded the 250 MB safety limit.")
                output.write(chunk)
        with zipfile.ZipFile(archive_path) as archive:
            root = extracted.resolve()
            members = archive.infolist()
            if len(members) > MAX_MODEL_ARCHIVE_ENTRIES:
                raise RuntimeError("The offline model archive contains too many files.")
            expanded_size = sum(member.file_size for member in members)
            if expanded_size > MAX_MODEL_EXTRACTED_BYTES:
                raise RuntimeError("The offline model archive exceeds the 500 MB extraction safety limit.")
            seen_paths = set()
            reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
            for member in members:
                # Reject Windows-specific path tricks before extracting an untrusted archive.
                name = member.filename
                parts = name.split("/")
                meaningful_parts = parts[:-1] if parts and parts[-1] == "" else parts
                invalid_component = any(
                    ":" in part or part.endswith((".", " "))
                    or any(ord(char) < 32 for char in part)
                    or part.split(".", 1)[0].upper() in reserved_names
                    for part in meaningful_parts
                )
                if (not name or name.startswith("/") or "\\" in name
                        or any(part in {"", ".", ".."} for part in meaningful_parts)
                        or not meaningful_parts or meaningful_parts[0] != model_name
                        or invalid_component):
                    raise RuntimeError("The model archive contains an unsafe file path.")
                normalized_name = "/".join(meaningful_parts).casefold()
                if normalized_name in seen_paths:
                    raise RuntimeError("The model archive contains duplicate file paths.")
                seen_paths.add(normalized_name)
                if member.flag_bits & 0x1:
                    raise RuntimeError("The model archive contains an encrypted file.")
                target = (extracted / name).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError("The model archive contains an unsafe file path.")
                mode = (member.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise RuntimeError("The model archive contains an unsafe file type.")
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
