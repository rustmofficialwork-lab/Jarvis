from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import owner_voice_setup


class OwnerVoiceSetupTests(unittest.TestCase):
    def test_enrollment_requires_explicit_confirmation_before_model_download(self):
        with patch.object(owner_voice_setup, "load_encoder") as load_encoder:
            with self.assertRaises(PermissionError):
                owner_voice_setup.enroll_owner_voice(confirmed=False)
        load_encoder.assert_not_called()

    def test_enrollment_saves_profile_and_removes_temporary_recordings(self):
        captured = {}

        def fake_recorder(count, destination):
            captured["directory"] = Path(destination)
            captured["count"] = count
            sample = Path(destination) / "sample.wav"
            sample.write_bytes(b"temporary owner voice data")
            captured["sample"] = sample
            return [sample] * 8

        profile = {"schema": 2, "sample_count": 8}
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(owner_voice_setup, "load_encoder", return_value=object()),
                patch.object(owner_voice_setup, "build_owner_profile", return_value=profile),
                patch.object(owner_voice_setup, "save_owner_profile") as save_profile,
            ):
                result = owner_voice_setup.enroll_owner_voice(
                    confirmed=True,
                    model_dir=Path(directory) / "model",
                    recorder=fake_recorder,
                )
        self.assertEqual(captured["count"], 8)
        self.assertEqual(result, {"sample_count": 8, "profile_saved": True})
        save_profile.assert_called_once_with(profile, keyring_module=None)
        self.assertFalse(captured["directory"].exists())
        self.assertFalse(captured["sample"].exists())


if __name__ == "__main__":
    unittest.main()
