from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from wakeword_dataset_recorder import record_clips


class EmptyStream:
    def __init__(self):
        self.closed = False
        self.stopped = False

    def read(self, frames: int, exception_on_overflow: bool = False) -> bytes:
        return b""

    def stop_stream(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakeAudio:
    def __init__(self):
        self.stream = EmptyStream()
        self.terminated = False

    def open(self, **kwargs):
        return self.stream

    def terminate(self):
        self.terminated = True


class WakewordRecorderValidationTests(unittest.TestCase):
    def test_rejects_invalid_labels_before_loading_audio_dependency(self):
        for label in ("", "owner", "positive "):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "label must be"):
                    record_clips(label, 1, Path("unused"))

    def test_rejects_invalid_counts_before_loading_audio_dependency(self):
        for count in (0, 501, 1.5, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "integer between 1 and 500"):
                    record_clips("positive", count, Path("unused"))

    def test_rejects_invalid_device_indices_before_loading_audio_dependency(self):
        for device_index in (-1, 0.5, True):
            with self.subTest(device_index=device_index):
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    record_clips("positive", 1, Path("unused"), device_index=device_index)

    def test_empty_microphone_reads_abort_and_release_audio(self):
        fake_audio = FakeAudio()
        fake_module = types.SimpleNamespace(PyAudio=lambda: fake_audio, paInt16=8)
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(sys.modules, {"pyaudio": fake_module}), patch(
                "wakeword_dataset_recorder.time.sleep"
            ):
                with self.assertRaisesRegex(RuntimeError, "empty audio chunk"):
                    record_clips("positive", 1, Path(directory))
        self.assertTrue(fake_audio.terminated)
        self.assertTrue(fake_audio.stream.stopped)
        self.assertTrue(fake_audio.stream.closed)


if __name__ == "__main__":
    unittest.main()
