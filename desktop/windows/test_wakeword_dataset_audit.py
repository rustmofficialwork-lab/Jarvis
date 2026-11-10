from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from wakeword_dataset_audit import audit_dataset, inspect_wav


def write_wav(path: Path, *, rate: int = 16_000, frames: int = 16_000,
              amplitude: int = 4_000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        sample = int(amplitude).to_bytes(2, "little", signed=True)
        output.writeframes(sample * frames)


class WakewordDatasetAuditTests(unittest.TestCase):
    def test_inspect_wav_accepts_valid_local_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "positive.wav"
            write_wav(path)
            result = inspect_wav(path)
            self.assertTrue(result["valid"])
            self.assertEqual(result["sample_rate"], 16_000)
            self.assertEqual(result["duration_seconds"], 1.0)

    def test_inspect_wav_reports_wrong_sample_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-rate.wav"
            write_wav(path, rate=8_000)
            result = inspect_wav(path)
            self.assertFalse(result["valid"])
            self.assertIn("expected 16000 Hz", result["issues"])

    def test_audit_fails_when_a_class_contains_an_invalid_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "positive").mkdir()
            (root / "negative").mkdir()
            write_wav(root / "positive" / "wrong-rate.wav", rate=8_000)
            write_wav(root / "negative" / "valid.wav")
            report = audit_dataset(root)
            self.assertEqual(report["status"], "needs-attention")
            self.assertEqual(report["classes"]["positive"]["invalid_count"], 1)
            self.assertIn("positive/ contains 1 invalid clip(s)", report["issues"])

    def test_audit_requires_both_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "positive").mkdir()
            (root / "negative").mkdir()
            write_wav(root / "positive" / "one.wav")
            report = audit_dataset(root)
            self.assertEqual(report["status"], "needs-attention")
            self.assertIn("missing or empty negative/ folder", report["issues"])


if __name__ == "__main__":
    unittest.main()
