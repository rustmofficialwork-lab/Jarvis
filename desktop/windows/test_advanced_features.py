"""Regression tests for focus sessions and recurring local workflows."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from advanced_features import AdvancedFeatureStore, parse_advanced_command, WORKFLOWS


class AdvancedFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AdvancedFeatureStore(Path(self.temp.name) / "advanced.sqlite3")
        self.now = datetime(2026, 10, 31, 10, 0).astimezone()

    def tearDown(self):
        self.temp.cleanup()

    def test_focus_session_persists_and_expires(self):
        end = self.store.start_focus(25, now=self.now)
        status = self.store.focus_status(now=self.now + timedelta(minutes=4))
        self.assertEqual(status["remaining_minutes"], 21)
        self.assertEqual(status["ends_at"], end)
        expired = self.store.focus_status(now=end + timedelta(seconds=1))
        self.assertIsNone(expired)

    def test_focus_duration_is_bounded(self):
        for value in (0, 241, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.start_focus(value, now=self.now)

    def test_automation_is_allowlisted_and_interval_bounded(self):
        with self.assertRaises(ValueError):
            self.store.add_automation("custom_shell", 60, now=self.now)
        for value in (4, 10081, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.add_automation("study", value, now=self.now)

    def test_due_automation_is_claimed_once_and_rescheduled(self):
        automation_id, due = self.store.add_automation("study", 30, now=self.now)
        claimed = self.store.claim_due_automations(now=due + timedelta(seconds=1))
        self.assertEqual([item["id"] for item in claimed], [automation_id])
        self.assertEqual(self.store.claim_due_automations(now=due + timedelta(seconds=2)), [])
        listed = self.store.list_automations()
        self.assertEqual(datetime.fromisoformat(listed[0]["next_run"]), due + timedelta(seconds=1) + timedelta(minutes=30))

    def test_delete_automation(self):
        automation_id, _ = self.store.add_automation("meeting", 60, now=self.now)
        self.assertTrue(self.store.delete_automation(automation_id))
        self.assertFalse(self.store.delete_automation(automation_id))
        self.assertEqual(self.store.list_automations(), [])

    def test_command_parser(self):
        self.assertEqual(parse_advanced_command("start pomodoro"), ("focus_start", 25))
        self.assertEqual(parse_advanced_command("start focus for 45 minutes"), ("focus_start", 45))
        self.assertEqual(parse_advanced_command("run study workflow"), ("workflow", "study"))
        self.assertEqual(parse_advanced_command("repeat deep work workflow every 60 minutes"),
                         ("automation_add", ("deep_work", 60)))
        self.assertEqual(parse_advanced_command("list automations"), ("automation_list", None))
        self.assertIsNone(parse_advanced_command("run arbitrary command"))

    def test_workflows_contain_only_fixed_local_commands(self):
        self.assertEqual(set(WORKFLOWS), {"study", "meeting", "deep_work"})
        for _label, commands in WORKFLOWS.values():
            self.assertTrue(commands)
            self.assertTrue(all(command in {"open notepad", "open calculator", "open browser", "open task manager"}
                                for command in commands))


if __name__ == "__main__":
    unittest.main()
