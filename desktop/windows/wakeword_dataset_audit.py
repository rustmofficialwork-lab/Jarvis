"""Audit locally recorded wake-word WAV clips without uploading or modifying audio.

Run from desktop/windows:
    py wakeword_dataset_audit.py --dataset-dir wakeword_dataset
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path
from typing import Any

EXPECTED_RATE = 16_000
EXPECTED_CHANNELS = 1
EXPECTED_WIDTH = 2


def inspect_wav(path: Path) -> dict[str, Any]:
    """Return format and signal-quality diagnostics for one WAV file."""
    result: dict[str, Any] = {"file": path.name, "valid": False, "issues": []}
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            duration = frames / rate if rate else 0.0
            result.update({
                "channels": channels,
                "sample_width_bytes": width,
                "sample_rate": rate,
                "duration_seconds": round(duration, 3),
            })
            if source.getcomptype() != "NONE":
                result["issues"].append("compressed WAV is not supported")
            if channels != EXPECTED_CHANNELS:
                result["issues"].append(f"expected {EXPECTED_CHANNELS} channel")
            if width != EXPECTED_WIDTH:
                result["issues"].append(f"expected {EXPECTED_WIDTH * 8}-bit PCM")
            if rate != EXPECTED_RATE:
                result["issues"].append(f"expected {EXPECTED_RATE} Hz")
            if duration < 0.5:
                result["issues"].append("clip is shorter than 0.5 seconds")
            if duration > 5.0:
                result["issues"].append("clip is longer than 5 seconds")

            sample_count = 0
            square_sum = 0
            peak = 0
            clipped = 0
            while True:
                raw = source.readframes(4096)
                if not raw:
                    break
                usable = len(raw) - (len(raw) % 2)
                for offset in range(0, usable, 2):
                    sample = int.from_bytes(raw[offset:offset + 2], "little", signed=True)
                    magnitude = abs(sample)
                    sample_count += 1
                    square_sum += sample * sample
                    peak = max(peak, magnitude)
                    if magnitude >= 32760:
                        clipped += 1

            rms = math.sqrt(square_sum / sample_count) if sample_count else 0.0
            result.update({
                "peak": peak,
                "rms": round(rms, 1),
                "clipped_sample_percent": round(100 * clipped / sample_count, 3) if sample_count else 0.0,
            })
            if sample_count == 0:
                result["issues"].append("empty audio")
            elif rms < 80:
                result["issues"].append("very quiet or silent clip")
            if sample_count and clipped / sample_count > 0.01:
                result["issues"].append("more than 1% of samples are clipped")
            result["valid"] = not result["issues"]
    except (OSError, EOFError, wave.Error) as exc:
        result["issues"].append(f"cannot read WAV: {exc}")
    return result


def audit_dataset(dataset_dir: Path) -> dict[str, Any]:
    """Audit positive and negative folders and return a JSON-serializable report."""
    root = Path(dataset_dir)
    report: dict[str, Any] = {"dataset_dir": str(root), "classes": {}, "issues": []}
    for label in ("positive", "negative"):
        folder = root / label
        files = sorted(folder.glob("*.wav")) if folder.is_dir() else []
        clips = [inspect_wav(path) for path in files]
        invalid = [clip for clip in clips if not clip["valid"]]
        report["classes"][label] = {
            "clip_count": len(clips),
            "valid_count": len(clips) - len(invalid),
            "invalid_count": len(invalid),
            "clips": clips,
        }
        if not files:
            report["issues"].append(f"missing or empty {label}/ folder")
    if not report["issues"]:
        report["status"] = "format-audit-passed"
    else:
        report["status"] = "needs-attention"
    report["note"] = (
        "A format audit is not a model-quality test. It does not measure false activations, "
        "missed detections, speaker diversity, or real-world robustness."
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local JARVIS wake-word recordings.")
    parser.add_argument("--dataset-dir", type=Path, default=Path("wakeword_dataset"))
    parser.add_argument("--json", action="store_true", help="print the full per-clip JSON report")
    args = parser.parse_args()
    report = audit_dataset(args.dataset_dir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Dataset: {report['dataset_dir']}")
        for label, summary in report["classes"].items():
            print(
                f"{label}: {summary['valid_count']}/{summary['clip_count']} valid "
                f"({summary['invalid_count']} need attention)"
            )
            for clip in summary["clips"]:
                if clip["issues"]:
                    print(f"  {clip['file']}: {', '.join(clip['issues'])}")
        print(report["status"])
        print(report["note"])
    return 0 if report["status"] == "format-audit-passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
