import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate_first_party_wakeword as evaluator


class WakewordEvaluationTests(unittest.TestCase):
    def test_prediction_requires_exactly_one_finite_model_score(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("NumPy is an optional runtime dependency")
        self.assertEqual(evaluator._score_from_prediction({"jarvis": [0.75]}), 0.75)
        with self.assertRaises(ValueError):
            evaluator._score_from_prediction({"a": [0.2], "b": [0.3]})
        with self.assertRaises(ValueError):
            evaluator._score_from_prediction({"jarvis": [float("nan")]})

    def test_evaluation_reports_recall_and_false_activations_per_hour(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "trained.onnx"
            model.write_bytes(b"model")
            positive = root / "positive"
            negative = root / "negative"
            positive.mkdir()
            negative.mkdir()
            (positive / "p1.wav").touch()
            (positive / "p2.wav").touch()
            (negative / "n1.wav").touch()

            def fake_score(model_path, wav_path, threshold, cooldown_seconds):
                if wav_path.parent.name == "positive":
                    return {"detected": wav_path.name == "p1.wav"}
                return {"activation_events": 2, "duration_seconds": 3600.0}

            with patch.object(evaluator, "score_clip", side_effect=fake_score):
                report = evaluator.evaluate(model, positive, negative, threshold=0.5)

        self.assertEqual(report["positive_clips"], 2)
        self.assertEqual(report["detected_positive_clips"], 1)
        self.assertEqual(report["missed_positive_clips"], 1)
        self.assertEqual(report["recall"], 0.5)
        self.assertEqual(report["false_activations_per_hour"], 2.0)

    def test_missing_evaluation_split_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "trained.onnx"
            model.write_bytes(b"model")
            (root / "positive").mkdir()
            (root / "negative").mkdir()
            with self.assertRaisesRegex(ValueError, "Both positive and negative"):
                evaluator.evaluate(model, root / "positive", root / "negative")

    def test_invalid_threshold_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "trained.onnx"
            model.write_bytes(b"model")
            (root / "positive").mkdir()
            (root / "negative").mkdir()
            with self.assertRaisesRegex(ValueError, "threshold"):
                evaluator.evaluate(model, root / "positive", root / "negative", threshold=1.0)


if __name__ == "__main__":
    unittest.main()
