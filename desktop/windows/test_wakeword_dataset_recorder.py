from __future__ import annotations

import unittest
from pathlib import Path

from wakeword_dataset_recorder import record_clips


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


if __name__ == "__main__":
    unittest.main()
