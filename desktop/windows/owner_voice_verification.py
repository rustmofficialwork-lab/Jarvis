"""Local ECAPA-TDNN owner-speaker verification using ONNX Runtime.

The model is downloaded only by an explicit enrollment action. Runtime verification
is offline and fails closed when the model or local owner profile is missing.
This is a convenience gate, not strong authentication or liveness detection.
"""
from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Any

MODEL_ID = "kenrunio/transcriber-speaker-onnx"
MODEL_REVISION = "4467ef1f92829ca0ff4bbdaa70d31f7d7d25c12c"
MODEL_SHA256 = "700b63064ee98981186f59f247d28e56f7f6ab265d8b50ebb450db5a8ce21dc7"
MODEL_FILENAME = "ecapa-any-length.onnx"
PROFILE_SCHEMA = 2
PROFILE_SERVICE = "JARVIS-Desktop-OwnerVoice"
PROFILE_USERNAME = "owner-ecapa-centroid-v2"
DEFAULT_COSINE_THRESHOLD = 0.25
SAMPLE_RATE = 16_000
MIN_AUDIO_SECONDS = 2.5


def _normalise(vector):
    import numpy as np

    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    if value.size == 0 or not np.isfinite(value).all():
        raise ValueError("Speaker embedding is empty or invalid.")
    norm = float(np.linalg.norm(value))
    if not math.isfinite(norm) or norm <= 1e-8:
        raise ValueError("Speaker embedding has no usable signal.")
    return value / norm


def ensure_model(model_dir: Path, allow_download: bool = False) -> Path:
    """Return the pinned local model file; download only after explicit opt-in."""
    target = Path(model_dir)
    model_path = target / MODEL_FILENAME
    if model_path.is_file() and model_path.stat().st_size > 10_000_000:
        with model_path.open("rb") as model_file:
            digest = hashlib.file_digest(model_file, "sha256").hexdigest()
        if digest == MODEL_SHA256:
            return model_path
        if not allow_download:
            raise RuntimeError("The local owner voice model failed its SHA-256 integrity check.")
        model_path.unlink()
    if not allow_download:
        raise FileNotFoundError("Owner voice model is not installed. Run the explicit owner-voice enrollment setup.")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install huggingface_hub from voice_identity_requirements.txt.") from exc
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(target),
        allow_patterns=[MODEL_FILENAME, "LICENSE", "README.md"],
    )
    if not model_path.is_file() or model_path.stat().st_size <= 10_000_000:
        raise RuntimeError("The downloaded ECAPA ONNX model is missing or incomplete.")
    with model_path.open("rb") as model_file:
        digest = hashlib.file_digest(model_file, "sha256").hexdigest()
    if digest != MODEL_SHA256:
        model_path.unlink(missing_ok=True)
        raise RuntimeError("The downloaded ECAPA ONNX model failed its SHA-256 integrity check.")
    return model_path


def load_encoder(model_dir: Path, allow_download: bool = False):
    """Load the local ONNX speaker encoder on CPU; no network at runtime."""
    model_path = ensure_model(model_dir, allow_download=allow_download)
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("ONNX Runtime is missing. Reinstall JARVIS voice dependencies.") from exc
    return ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])


def _read_wav(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != SAMPLE_RATE:
            raise ValueError(f"{Path(path).name}: expected 16 kHz, mono, 16-bit PCM WAV.")
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    if samples.size < int(SAMPLE_RATE * MIN_AUDIO_SECONDS):
        raise ValueError(f"{Path(path).name}: at least {MIN_AUDIO_SECONDS:.1f} seconds of speech is required.")
    return samples.astype(np.float32) / 32768.0


def embed_samples(samples, encoder):
    """Extract a unit-length ECAPA embedding from 16 kHz mono float audio."""
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if audio.size < int(SAMPLE_RATE * MIN_AUDIO_SECONDS):
        raise ValueError(f"At least {MIN_AUDIO_SECONDS:.1f} seconds of audio is required.")
    if not np.isfinite(audio).all():
        raise ValueError("Audio contains invalid samples.")
    outputs = encoder.run(
        ["emb"],
        {
            "wav": audio[np.newaxis, :].astype(np.float32),
            "lens": np.asarray([1.0], dtype=np.float32),
        },
    )
    return _normalise(np.asarray(outputs[0])[0, 0])


def build_owner_profile(wav_paths, encoder) -> dict[str, Any]:
    """Build a normalised centroid from at least five separately prompted clips."""
    import numpy as np

    paths = list(wav_paths)
    if len(paths) < 5:
        raise ValueError("At least five owner enrollment clips are required.")
    vectors = [embed_samples(_read_wav(path), encoder) for path in paths]
    dimensions = {int(vector.size) for vector in vectors}
    if len(dimensions) != 1:
        raise ValueError("Speaker model returned inconsistent embedding dimensions.")
    centroid = _normalise(np.mean(np.stack(vectors), axis=0))
    return {
        "schema": PROFILE_SCHEMA,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "embedding": [float(item) for item in centroid],
        "sample_count": len(vectors),
    }


def save_owner_profile(profile: dict[str, Any], keyring_module=None) -> None:
    """Store only the derived voice embedding in the OS credential vault."""
    if keyring_module is None:
        import keyring as keyring_module
    if profile.get("schema") != PROFILE_SCHEMA or profile.get("model_id") != MODEL_ID:
        raise ValueError("Unsupported owner voice profile.")
    vector = _normalise(profile.get("embedding", []))
    payload = dict(profile)
    payload["embedding"] = [float(item) for item in vector]
    keyring_module.set_password(
        PROFILE_SERVICE, PROFILE_USERNAME,
        json.dumps(payload, separators=(",", ":"), allow_nan=False),
    )


def load_owner_profile(keyring_module=None) -> dict[str, Any] | None:
    if keyring_module is None:
        import keyring as keyring_module
    raw = keyring_module.get_password(PROFILE_SERVICE, PROFILE_USERNAME)
    if not raw:
        return None
    try:
        profile = json.loads(raw)
        if (not isinstance(profile, dict)
                or profile.get("schema") != PROFILE_SCHEMA
                or profile.get("model_id") != MODEL_ID
                or profile.get("model_revision") != MODEL_REVISION):
            return None
        profile["embedding"] = [float(item) for item in profile["embedding"]]
        _normalise(profile["embedding"])
        return profile
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def delete_owner_profile(keyring_module=None) -> None:
    if keyring_module is None:
        import keyring as keyring_module
    try:
        keyring_module.delete_password(PROFILE_SERVICE, PROFILE_USERNAME)
    except Exception as exc:
        if "not found" not in str(exc).casefold() and "no password" not in str(exc).casefold():
            raise


def verify_samples(samples, encoder, profile: dict[str, Any] | None,
                   threshold: float = DEFAULT_COSINE_THRESHOLD) -> tuple[bool, float | None]:
    """Compare a live utterance with the local centroid; uncertain cases reject."""
    import numpy as np

    if profile is None:
        return False, None
    try:
        if not math.isfinite(float(threshold)) or not -1.0 <= float(threshold) <= 1.0:
            return False, None
        candidate = embed_samples(samples, encoder)
        enrolled = _normalise(profile.get("embedding", []))
        if candidate.size != enrolled.size:
            return False, None
        score = float(np.dot(candidate, enrolled))
        if not math.isfinite(score):
            return False, None
        return score >= float(threshold), score
    except (TypeError, ValueError, RuntimeError):
        return False, None


def verify_pcm_bytes(raw_pcm: bytes, encoder, profile,
                     threshold: float = DEFAULT_COSINE_THRESHOLD):
    """Verify 16-bit mono 16 kHz PCM bytes captured by the wake-word ring buffer."""
    import numpy as np

    if not raw_pcm or len(raw_pcm) % 2:
        return False, None
    samples = np.frombuffer(raw_pcm, dtype="<i2").astype(np.float32) / 32768.0
    return verify_samples(samples, encoder, profile, threshold=threshold)
