"""Install a locally trained JARVIS wake-word ONNX model.

Run from desktop/windows:
    py install_first_party_wakeword.py --model C:\\path\\to\\jarvis_first_party.onnx --confirm
"""
from __future__ import annotations

import argparse
from pathlib import Path

from jarvis_desktop import install_first_party_wakeword_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a custom-trained JARVIS wake-word model.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--confirm", action="store_true", help="confirm installation of this locally trained model")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Pass --confirm after checking that this is your trained JARVIS ONNX model.")
    try:
        destination = install_first_party_wakeword_model(args.model)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Model installation failed: {exc}\n")
    print(f"First-party JARVIS wake-word model installed: {destination}")
    print("Restart JARVIS voice listening to use it. The app prefers this model over the legacy publisher model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
