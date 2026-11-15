"""Interactive, local-only wake-word microphone check for Windows.

No audio is saved or uploaded. Run from this folder with:
    py wakeword_mic_test.py
List input devices with:
    py wakeword_mic_test.py --list-devices
Select one with:
    py wakeword_mic_test.py --device-index 2
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model

from jarvis_desktop import (
    JARVIS_WAKEWORD_MODEL,
    prepare_openwakeword_assets,
    update_wakeword_activation,
)


CHUNK_SIZE = 1280  # 80 ms at 16 kHz


def print_input_devices(audio) -> None:
    """Print available Windows input devices with the index accepted by PyAudio."""
    found = False
    for index in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(index)
        if int(info.get("maxInputChannels", 0)) > 0:
            found = True
            print(
                f"  [{index}] {info.get('name', 'Unknown input')} "
                f"(channels: {int(info.get('maxInputChannels', 0))}, "
                f"default rate: {int(info.get('defaultSampleRate', 0))} Hz)"
            )
    if not found:
        print("No audio input devices were reported by Windows/PyAudio.")


def capture_phase(
    audio,
    detector,
    model_name: str,
    label: str,
    seconds: int,
    threshold: float,
    device_index: int | None = None,
) -> dict:
    input(f"\n{label}\nPress Enter when ready...")
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK_SIZE,
    )
    end_at = time.monotonic() + seconds
    streak = 0
    last_activation = 0.0
    activations = 0
    max_score = 0.0
    frames = 0
    try:
        while time.monotonic() < end_at:
            raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            expected_bytes = CHUNK_SIZE * 2  # 16-bit mono PCM
            if len(raw) != expected_bytes:
                raise RuntimeError(
                    "Microphone returned an empty or incomplete audio frame "
                    f"({len(raw)} of {expected_bytes} bytes). Check the input device and reconnect it."
                )
            frame = np.frombuffer(raw, dtype=np.int16)
            scores = detector.predict(frame)
            score = float(scores.get(model_name, 0.0))
            max_score = max(max_score, score)
            activated, streak = update_wakeword_activation(
                score, streak, threshold=threshold, required_frames=2
            )
            now = time.monotonic()
            if activated and now - last_activation >= 2.0:
                activations += 1
                last_activation = now
                streak = 0
            frames += 1
    finally:
        try:
            stream.stop_stream()
        finally:
            stream.close()
        detector.reset()
    return {
        "phase": label,
        "seconds": seconds,
        "frames": frames,
        "max_score": max_score,
        "activations": activations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Test JARVIS wake-word detection on this PC.")
    parser.add_argument("--model", type=Path, default=JARVIS_WAKEWORD_MODEL)
    parser.add_argument("--device-index", type=int, default=None, help="PyAudio input device index; default input is used when omitted.")
    parser.add_argument("--list-devices", action="store_true", help="List Windows audio input devices and exit.")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not math.isfinite(args.threshold) or not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be a finite number between 0 and 1")

    audio = None
    try:
        audio = pyaudio.PyAudio()
        if args.list_devices:
            print("Available microphone/input devices:")
            print_input_devices(audio)
            return 0

        if args.device_index is not None:
            if args.device_index < 0 or args.device_index >= audio.get_device_count():
                print(f"Invalid input device index: {args.device_index}")
                print_input_devices(audio)
                return 2
            selected = audio.get_device_info_by_index(args.device_index)
            if int(selected.get("maxInputChannels", 0)) < 1:
                print(f"Device {args.device_index} is not an audio input device.")
                print_input_devices(audio)
                return 2
            print(f"Using microphone [{args.device_index}]: {selected.get('name', 'Unknown input')}")
        else:
            print("Using the Windows/PyAudio default input device.")

        if not args.model.is_file():
            print(f"Wake-word model not found: {args.model}")
            print("Complete the in-app Set up wake word step first.")
            return 2

        print("Loading the local Jarvis wake-word model…")
        # Store shared runtime files in the current user's writable AppData.
        runtime_paths = prepare_openwakeword_assets(openwakeword, args.model)
        detector = Model(
            wakeword_models=[str(args.model)],
            inference_framework="onnx",
            **runtime_paths,
        )
        results = []
        print("\nJARVIS microphone test")
        print("- Quiet phase: stay quiet; this measures false activations.")
        print("- Speech phase: say 'Jarvis' clearly five times, with a short pause.")
        print("- Background phase: keep ordinary room/TV/fan noise at your normal level; do not say the wake word.")
        results.append(capture_phase(audio, detector, args.model.stem, "QUIET ROOM — 12 seconds; stay silent.", 12, args.threshold, args.device_index))
        results.append(capture_phase(audio, detector, args.model.stem, "WAKE WORD — 18 seconds; say Jarvis five times.", 18, args.threshold, args.device_index))
        results.append(capture_phase(audio, detector, args.model.stem, "BACKGROUND NOISE — 15 seconds; do not say Jarvis.", 15, args.threshold, args.device_index))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Microphone/model test failed: {exc}")
        return 1
    finally:
        if audio is not None:
            audio.terminate()

    print("\nResults (audio was not saved):")
    for item in results:
        print(
            f"- {item['phase']}: {item['activations']} activation(s), "
            f"peak score {item['max_score']:.3f}, {item['frames']} frames"
        )
    quiet, speech, noise = results
    print("\nAssessment:")
    print("PASS: no false activations in quiet phase." if quiet["activations"] == 0 else "CHECK: activation(s) occurred during quiet; inspect mic noise/placement.")
    print("PASS: wake word was detected." if speech["activations"] > 0 else "CHECK: no wake word detected; check input device, mic level, pronunciation and distance.")
    print("PASS: no false activations in background phase." if noise["activations"] == 0 else "CHECK: background noise caused activation(s); try a different mic position or reduce speaker feedback.")
    print("\nThis is a local spot-check, not a certified accuracy benchmark. Repeat in the room and with the microphone you normally use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
