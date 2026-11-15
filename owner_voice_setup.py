"""Explicit local owner-voice enrollment and profile reset for JARVIS.

Run from desktop/windows:
    py owner_voice_setup.py --enroll --confirm
    py owner_voice_setup.py --reset --confirm

The enrollment WAV files are temporary and deleted after the local profile is saved.
Only the derived ECAPA embedding is stored in Windows Credential Manager.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from owner_voice_verification import (
    build_owner_profile,
    delete_owner_profile,
    load_encoder,
    save_owner_profile,
)
from speaker_enrollment_recorder import record_enrollment

MODEL_DIR = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "JARVISDesktop" / "speaker_model"


def enroll_owner_voice(*, confirmed: bool = False, model_dir: Path = MODEL_DIR,
                       keyring_module=None, recorder=record_enrollment) -> dict:
    if not confirmed:
        raise PermissionError("Explicit owner-voice enrollment confirmation is required.")
    encoder = load_encoder(model_dir, allow_download=True)
    with tempfile.TemporaryDirectory(prefix="jarvis-owner-enrollment-") as temporary:
        clips = recorder(8, Path(temporary))
        profile = build_owner_profile(clips, encoder)
        save_owner_profile(profile, keyring_module=keyring_module)
    return {"sample_count": profile["sample_count"], "profile_saved": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up or reset local JARVIS owner voice verification.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--enroll", action="store_true")
    action.add_argument("--reset", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="confirm local microphone enrollment or profile deletion")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Pass --confirm only after reviewing the local voice-data notice.")
    try:
        if args.reset:
            delete_owner_profile()
            print("Local owner voice profile deleted from the OS credential vault.")
            return 0
        result = enroll_owner_voice(confirmed=True)
        print(f"Owner voice profile created from {result['sample_count']} local clips.")
        print("Raw enrollment WAV files were deleted. Voice verification is a convenience gate, not strong authentication.")
        return 0
    except (OSError, RuntimeError, ValueError, PermissionError) as exc:
        parser.exit(1, f"Owner voice setup failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
