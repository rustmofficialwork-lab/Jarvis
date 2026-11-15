import tempfile
import unittest
from pathlib import Path

from brain_engine import (
    BrainEngine,
    create_task_plan,
    diagnose_failure,
    evaluate_task,
)
from memory_store import MemoryStore


class BrainEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.engine = BrainEngine(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_is_bounded_and_deduplicated(self):
        plan = create_task_plan("Prepare report", ["Collect data", "Write report", "Collect data"])
        self.assertEqual(plan.steps, ("Collect data", "Write report"))
        with self.assertRaises(ValueError):
            create_task_plan("Prepare report", ["x"] * 9)

    def test_evaluation_never_marks_missing_steps_complete(self):
        plan = create_task_plan("Install app", ["Check requirements", "Install", "Verify launch"])
        result = evaluate_task(plan, ["Check requirements", "invented step"], ["Installer failed"])
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.completed, ("Check requirements",))
        self.assertEqual(result.remaining, ("Install", "Verify launch"))

    def test_evaluation_requires_evidence_for_completion(self):
        plan = create_task_plan("Run checks", ["Backend checks", "Windows checks"])
        self.assertEqual(evaluate_task(plan, []).status, "not_started")
        self.assertEqual(evaluate_task(plan, plan.steps).status, "completed")

    def test_diagnostics_classify_common_failures(self):
        self.assertEqual(diagnose_failure("connection timed out").category, "connectivity")
        self.assertEqual(diagnose_failure("HTTP 401 invalid API key").category, "authentication")
        self.assertEqual(diagnose_failure("HTTP 429 rate limit").category, "rate_limit")
        self.assertEqual(diagnose_failure("Ollama model not found").category, "offline_model")
        self.assertEqual(diagnose_failure("permission denied").category, "permission")
        self.assertEqual(diagnose_failure("unexpected exception").category, "unknown")

    def test_local_memory_context_respects_privacy_switch(self):
        self.store.add("Prefers concise Hinglish replies", "preference")
        self.assertEqual(self.engine.context_for("Hinglish", enabled=False), [])
        self.assertTrue(self.engine.context_for("Hinglish", enabled=True))

    def test_learning_requires_explicit_user_feedback(self):
        with self.assertRaises(PermissionError):
            self.engine.learn_preference("Prefers short answers", explicit=False)
        item = self.engine.learn_preference("Prefers short answers", explicit=True)
        self.assertEqual(item["category"], "preference")

    def test_learning_store_rejects_secrets(self):
        with self.assertRaises(ValueError):
            self.engine.learn_preference("My API key is secret", explicit=True)


if __name__ == "__main__":
    unittest.main()
