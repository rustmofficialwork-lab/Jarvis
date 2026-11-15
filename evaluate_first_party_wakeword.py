"""Evaluate a trained JARVIS openWakeWord ONNX model on held-out WAV recordings.

Expected layout:
  evaluation/positive/*.wav  # each clip contains one intentional "Jarvis"
  evaluation/negative/*.wav  # continuous speech/noise without "Jarvis"

All audio must be mono, 16-bit PCM, 16 kHz. The tool reports clip recall and
false activations per hour; it never changes the activation threshold.
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path
from typing import Any

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1_280  # 80 ms, the openWakeWord streaming frame size


def read_pcm16(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as audio:
        if audio.getcomptype() != "NONE":
            raise ValueError(f"{path}: compressed WAV is unsupported")
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != SAMPLE_RATE:
            raise ValueError(f"{path}: expected mono 16-bit PCM at {SAMPLE_RATE} Hz")
        frames = audio.readframes(audio.getnframes())
    if not frames:
        raise ValueError(f"{path}: empty WAV")
    return np.frombuffer(frames, dtype="<i2").copy(), len(frames) / 2 / SAMPLE_RATE


def _score_from_prediction(prediction: Any) -> float:
    """Extract the single model score returned by openWakeWord Model.predict."""
    import numpy as np

    if not isinstance(prediction, dict) or len(prediction) != 1:
        raise ValueError("Expected exactly one wake-word model prediction")
    values = np.asarray(next(iter(prediction.values())), dtype=float).reshape(-1)
    if values.size == 0:
        raise ValueError("Wake-word model returned an empty score")
    score = float(values[-1])
    if not math.isfinite(score):
        raise ValueError("Wake-word model returned a non-finite score")
    return score


def score_clip(model_path: Path, wav_path: Path, threshold: float,
               cooldown_seconds: float = 1.5) -> dict[str, Any]:
    """Score one WAV; count rising-edge detections separated by a cooldown."""
    import numpy as np
    from openwakeword.model import Model

    pcm, duration = read_pcm16(wav_path)
    model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
    scores: list[float] = []
    last_activation = -math.inf
    activations = 0
    consecutive = 0
    armed = True
    for offset in range(0, len(pcm), FRAME_SAMPLES):
        frame = pcm[offset:offset + FRAME_SAMPLES]
        if frame.size < FRAME_SAMPLES:
            frame = np.pad(frame, (0, FRAME_SAMPLES - frame.size))
        score = _score_from_prediction(model.predict(frame))
        scores.append(score)
        frame_time = offset / SAMPLE_RATE
        if score >= threshold:
            consecutive += 1
            if consecutive >= 2 and armed:
                if frame_time - last_activation >= cooldown_seconds:
                    activations += 1
                    last_activation = frame_time
                armed = False
        else:
            consecutive = 0
            armed = True
    return {
        "file": wav_path.name,
        "duration_seconds": round(duration, 3),
        "max_score": round(max(scores), 6),
        "detected": activations > 0,
        "activation_events": activations,
    }


def evaluate(model_path: Path, positive_dir: Path, negative_dir: Path,
             threshold: float = 0.5, cooldown_seconds: float = 1.5) -> dict[str, Any]:
    model_path = Path(model_path)
    if not model_path.is_file() or model_path.suffix.casefold() != ".onnx":
        raise ValueError("A trained .onnx model file is required")
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be strictly between 0 and 1")
    if cooldown_seconds < 0:
        raise ValueError("cooldown_seconds cannot be negative")
    positive_files = sorted(Path(positive_dir).glob("*.wav"))
    negative_files = sorted(Path(negative_dir).glob("*.wav"))
    if not positive_files or not negative_files:
        raise ValueError("Both positive and negative evaluation folders must contain WAV files")

    positive = [score_clip(model_path, path, threshold, cooldown_seconds) for path in positive_files]
    negative = [score_clip(model_path, path, threshold, cooldown_seconds) for path in negative_files]
    positive_count = len(positive)
    detected_count = sum(item["detected"] for item in positive)
    negative_hours = sum(item["duration_seconds"] for item in negative) / 3600.0
    false_events = sum(item["activation_events"] for item in negative)
    return {
        "model": str(model_path),
        "threshold": threshold,
        "positive_clips": positive_count,
        "detected_positive_clips": detected_count,
        "missed_positive_clips": positive_count - detected_count,
        "recall": round(detected_count / positive_count, 6),
        "negative_audio_hours": round(negative_hours, 6),
        "false_activation_events": false_events,
        "false_activations_per_hour": round(false_events / negative_hours, 6) if negative_hours else None,
        "positive_results": positive,
        "negative_results": negative,
        "warning": (
            "Evaluation is only meaningful when these recordings are held out from training, "
            "cover independent sessions and representative rooms/noise, and include hours of "
            "negative audio. Do not tune a threshold on the final test set."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate JARVIS wake-word recall and false activations.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--positive-dir", type=Path, required=True)
    parser.add_argument("--negative-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--cooldown-seconds", type=float, default=1.5)
    parser.add_argument("--output", type=Path, default=Path("wakeword-evaluation.json"))
    args = parser.parse_args()
    try:
        report = evaluate(args.model, args.positive_dir, args.negative_dir,
                          args.threshold, args.cooldown_seconds)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        parser.exit(1, f"Evaluation failed: {exc}\n")
    print(f"Recall: {report['detected_positive_clips']}/{report['positive_clips']} "
          f"({report['recall']:.1%})")
    print(f"False activations/hour: {report['false_activations_per_hour']}")
    print(f"Report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
