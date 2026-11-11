"""Local ECAPA-TDNN owner-speaker verification for JARVIS.

The model is downloaded only by an explicit enrollment action. Runtime verification
is offline and fails closed when the model or local owner profile is missing.
This is a convenience gate, not strong authentication or liveness detection.
"""
from __future__ import annotations

import json
import math
import wave
from pathlib import Path
from typing import Any

MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_REVISION = "b3e6e444667c2bc4f3d62ba2531a0cc784dd04f1"
PROFILE_SCHEMA = 1
PROFILE_SERVICE = "JARVIS-Desktop-OwnerVoice"
PROFILE_USERNAME = "owner-ecapa-centroid-v1"
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
    """Return the pinned local model directory; download only after explicit opt-in."""
    target = Path(model_dir)
    if (target / "hyperparams.yaml").is_file():
        return target
    if not allow_download:
        raise FileNotFoundError("Owner voice model is not installed. Run the explicit owner-voice enrollment setup.")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install voice identity dependencies from voice_identity_requirements.txt.") from exc
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(target),
    )
    if not (target / "hyperparams.yaml").is_file():
        raise RuntimeError("The downloaded speaker model is incomplete.")
    return target


def load_encoder(model_dir: Path, allow_download: bool = False):
    """Load the pinned ECAPA encoder on CPU; no network access during normal runtime."""
    path = ensure_model(model_dir, allow_download=allow_download)
    try:
        from speechbrain.inference.classifiers import EncoderClassifier
    except ImportError as exc:
        raise RuntimeError("SpeechBrain is missing. Install voice_identity_requirements.txt.") from exc
    return EncoderClassifier.from_hparams(
        source=str(path),
        savedir=str(path),
        run_opts={"device": "cpu"},
    )


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
    """Extract one L2-normalised ECAPA embedding from 16 kHz mono float audio."""
    import numpy as np
    import torch

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if audio.size < int(SAMPLE_RATE * MIN_AUDIO_SECONDS):
        raise ValueError(f"At least {MIN_AUDIO_SECONDS:.1f} seconds of audio is required.")
    if not np.isfinite(audio).all():
        raise ValueError("Audio contains invalid samples.")
    signal = torch.from_numpy(audio).unsqueeze(0)
    with torch.no_grad():
        embedding = encoder.encode_batch(signal).detach().cpu().numpy().reshape(-1)
    return _normalise(embedding)


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
        # Missing profile is already the desired state.
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
