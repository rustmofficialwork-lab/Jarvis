"""Record a local owner-voice enrollment set for future speaker verification.

Run from desktop/windows:
    py speaker_enrollment_recorder.py --count 20

This records only after an explicit command. WAV files stay on this computer;
the script does not upload, identify, or verify anyone.
"""
from __future__ import annotations

import argparse
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_RATE = 16_000
CHANNELS = 1
CLIP_SECONDS = 3.0
PROMPTS = (
    "Today I am setting up my JARVIS voice profile.",
    "JARVIS, please listen carefully to my voice.",
    "I use my computer for learning and everyday tasks.",
    "This is another sample of my normal speaking voice.",
    "I may speak a little faster or slower in different situations.",
)


def record_enrollment(count: int, output_dir: Path, device_index: int | None = None) -> list[Path]:
    """Capture prompted, consent-based owner speech clips locally."""
    if isinstance(count, bool) or not isinstance(count, int) or not 5 <= count <= 200:
        raise ValueError("count must be an integer between 5 and 200")
    if device_index is not None and (
        isinstance(device_index, bool) or not isinstance(device_index, int) or device_index < 0
    ):
        raise ValueError("device_index must be a non-negative integer")

    try:
        import pyaudio
    except ImportError as exc:
        raise RuntimeError("PyAudio is required. Install desktop voice requirements first.") from exc

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    audio = pyaudio.PyAudio()
    stream = None
    written: list[Path] = []
    bytes_per_clip = int(SAMPLE_RATE * CLIP_SECONDS) * 2
    try:
        if device_index is not None:
            info = audio.get_device_info_by_index(device_index)
            if int(info.get("maxInputChannels", 0)) < 1:
                raise ValueError(f"Audio device {device_index} is not an input device")
        stream = audio.open(
            format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
            input=True, input_device_index=device_index, frames_per_buffer=1024,
        )
        print("Owner voice enrollment recording. Speak naturally; files remain local.")
        print("Use only your own voice. You can stop at any time with Ctrl+C.")
        for index in range(count):
            prompt = PROMPTS[index % len(PROMPTS)]
            print(f"Clip {index + 1}/{count}: {prompt}")
            for remaining in (3, 2, 1):
                print(f"  Recording in {remaining}…")
                time.sleep(1)
            captured = bytearray()
            while len(captured) < bytes_per_clip:
                captured.extend(stream.read(1024, exception_on_overflow=False))
            captured = captured[:bytes_per_clip]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            path = destination / f"owner_{index + 1:04d}_{stamp}.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(CHANNELS)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                output.writeframes(bytes(captured))
            written.append(path)
            print(f"  Saved locally: {path.name}")
    finally:
        # Always release the PyAudio host API, even if stopping or closing the
        # input stream raises while handling a recording/device error.
        try:
            if stream is not None:
                try:
                    stream.stop_stream()
                finally:
                    stream.close()
        finally:
            audio.terminate()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Record local owner voice enrollment samples.")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("speaker_dataset/owner"))
    parser.add_argument("--device-index", type=int, default=None)
    args = parser.parse_args()
    try:
        files = record_enrollment(args.count, args.output_dir, args.device_index)
    except KeyboardInterrupt:
        print("\nRecording cancelled. Completed clips remain in the local output folder.")
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Recording failed: {exc}\n")
    print(f"Finished: {len(files)} local owner clips saved under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
