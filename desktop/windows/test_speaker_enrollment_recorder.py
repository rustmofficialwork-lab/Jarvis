from __future__ import annotations

import unittest
from pathlib import Path

from speaker_enrollment_recorder import PROMPTS, record_enrollment


class SpeakerEnrollmentRecorderTests(unittest.TestCase):
    def test_rejects_too_few_clips_before_audio_dependency_is_loaded(self):
        with self.assertRaisesRegex(ValueError, "between 5 and 200"):
            record_enrollment(4, Path("unused"))

    def test_rejects_too_many_clips_before_audio_dependency_is_loaded(self):
        with self.assertRaisesRegex(ValueError, "between 5 and 200"):
            record_enrollment(201, Path("unused"))

    def test_has_multiple_prompts_for_varied_speech(self):
        self.assertGreaterEqual(len(PROMPTS), 3)
        self.assertTrue(all(isinstance(prompt, str) and prompt.strip() for prompt in PROMPTS))


if __name__ == "__main__":
    unittest.main()
