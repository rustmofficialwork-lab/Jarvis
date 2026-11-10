from __future__ import annotations

import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from speaker_enrollment_recorder import PROMPTS, record_enrollment


class FakeStream:
    def __init__(self, *, fail_close: bool = False):
        self.closed = False
        self.stopped = False
        self.fail_close = fail_close

    def read(self, frames: int, exception_on_overflow: bool = False) -> bytes:
        return b"\\x01\\x00" * frames

    def stop_stream(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("simulated stream close failure")


class FakeAudio:
    def __init__(self, *, fail_close: bool = False):
        self.stream = FakeStream(fail_close=fail_close)
        self.terminated = False

    def get_device_info_by_index(self, index: int) -> dict:
        return {"maxInputChannels": 1}

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        return self.stream

    def terminate(self) -> None:
        self.terminated = True


class SpeakerEnrollmentRecorderTests(unittest.TestCase):
    def test_rejects_invalid_clip_counts_before_audio_dependency_is_loaded(self):
        for count in (4, 201, 5.5, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "integer between 5 and 200"):
                    record_enrollment(count, Path("unused"))

    def test_rejects_invalid_device_index_before_audio_dependency_is_loaded(self):
        for device_index in (-1, 1.5, True):
            with self.subTest(device_index=device_index):
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    record_enrollment(5, Path("unused"), device_index=device_index)

    def test_records_valid_mono_16khz_pcm_wav_files_and_releases_audio(self):
        fake_audio = FakeAudio()
        fake_module = types.SimpleNamespace(PyAudio=lambda: fake_audio, paInt16=8)
        with tempfile.TemporaryDirectory() as directory, \\
                patch.dict(sys.modules, {"pyaudio": fake_module}), \\
                patch("speaker_enrollment_recorder.time.sleep"):
            files = record_enrollment(5, Path(directory), device_index=0)

            self.assertEqual(len(files), 5)
            self.assertTrue(all(path.is_file() for path in files))
            with wave.open(str(files[0]), "rb") as source:
                self.assertEqual(source.getnchannels(), 1)
                self.assertEqual(source.getsampwidth(), 2)
                self.assertEqual(source.getframerate(), 16_000)
                self.assertEqual(source.getnframes(), 48_000)
            self.assertEqual(fake_audio.open_kwargs["rate"], 16_000)
            self.assertTrue(fake_audio.stream.stopped)
            self.assertTrue(fake_audio.stream.closed)
            self.assertTrue(fake_audio.terminated)

    def test_audio_api_is_terminated_even_if_stream_close_fails(self):
        fake_audio = FakeAudio(fail_close=True)
        fake_module = types.SimpleNamespace(PyAudio=lambda: fake_audio, paInt16=8)
        with tempfile.TemporaryDirectory() as directory, \\
                patch.dict(sys.modules, {"pyaudio": fake_module}), \\
                patch("speaker_enrollment_recorder.time.sleep"):
            with self.assertRaisesRegex(OSError, "stream close failure"):
                record_enrollment(5, Path(directory))
        self.assertTrue(fake_audio.terminated)

    def test_has_multiple_prompts_for_varied_speech(self):
        self.assertGreaterEqual(len(PROMPTS), 3)
        self.assertTrue(all(isinstance(prompt, str) and prompt.strip() for prompt in PROMPTS))


if __name__ == "__main__":
    unittest.main()
