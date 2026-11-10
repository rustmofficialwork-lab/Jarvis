"""Collect local, consent-based audio clips for training a first-party JARVIS wake word.

Examples (run from desktop/windows):
    py wakeword_dataset_recorder.py --label positive --count 30
    py wakeword_dataset_recorder.py --label negative --count 30

Positive clips: say only "Jarvis" once, naturally, after the prompt.
Negative clips: do not say "Jarvis"; capture ordinary room noise or unrelated speech.
Audio stays on this computer. This utility never uploads or transmits recordings.
"""
from __future__ import annotations

import argparse
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_RATE = 16_000
CLIP_SECONDS = 1.5
CHANNELS = 1


def record_clips(label: str, count: int, output_dir: Path, device_index: int | None = None) -> list[Path]:
    """Record fixed-length WAV clips from a local microphone."""
    if label not in {"positive", "negative"}:
        raise ValueError("label must be 'positive' or 'negative'")
    if count < 1 or count > 500:
        raise ValueError("count must be between 1 and 500")

    try:
        import pyaudio
    except ImportError as exc:
        raise RuntimeError("PyAudio is required. Install the desktop voice requirements first.") from exc

    destination = Path(output_dir) / label
    destination.mkdir(parents=True, exist_ok=True)
    audio = pyaudio.PyAudio()
    stream = None
    written: list[Path] = []
    frames_per_clip = int(SAMPLE_RATE * CLIP_SECONDS)
    try:
        if device_index is not None:
            info = audio.get_device_info_by_index(device_index)
            if int(info.get("maxInputChannels", 0)) < 1:
                raise ValueError(f"Audio device {device_index} is not an input device")
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024,
        )
        print(f"Recording {count} {label} clips. Audio remains local.")
        for index in range(count):
            if label == "positive":
                print(f"Clip {index + 1}/{count}: say 'Jarvis' once after the countdown.")
            else:
                print(f"Clip {index + 1}/{count}: stay natural; do NOT say 'Jarvis'.")
            for remaining in (3, 2, 1):
                print(f"  {remaining}…")
                time.sleep(1)
            captured = bytearray()
            while len(captured) < frames_per_clip * 2:
                chunk = stream.read(1024, exception_on_overflow=False)
                captured.extend(chunk)
            captured = captured[: frames_per_clip * 2]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            path = destination / f"{label}_{index + 1:04d}_{stamp}.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(CHANNELS)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                output.writeframes(bytes(captured))
            written.append(path)
            print(f"  Saved locally: {path.name}")
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            finally:
                stream.close()
        audio.terminate()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Record local JARVIS wake-word training samples.")
    parser.add_argument("--label", required=True, choices=("positive", "negative"))
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("wakeword_dataset"))
    parser.add_argument("--device-index", type=int, default=None)
    args = parser.parse_args()
    try:
        files = record_clips(args.label, args.count, args.output_dir, args.device_index)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Recording failed: {exc}\n")
    print(f"Finished: {len(files)} local WAV clips saved under {args.output_dir / args.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
