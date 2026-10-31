import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from reminders import ReminderStore, parse_reminder_command


class ReminderStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reminders.sqlite3"
        self.store = ReminderStore(self.path)

    def test_relative_english_reminder(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        message, due = parse_reminder_command("remind me in 10 minutes to drink water", now)
        self.assertEqual(message, "drink water")
        self.assertEqual(due, now + timedelta(minutes=10))

    def test_relative_hinglish_reminder(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        message, due = parse_reminder_command("mujhe 2 hours baad meeting yaad dilana", now)
        self.assertEqual(message, "meeting")
        self.assertEqual(due, now + timedelta(hours=2))

    def test_clock_reminder_rolls_to_tomorrow_if_time_passed(self):
        now = datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)
        message, due = parse_reminder_command("remind me at 09:30 to call home", now)
        self.assertEqual(message, "call home")
        self.assertEqual(due, datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc))

    def test_invalid_clock_is_rejected(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            parse_reminder_command("remind me at 25:90 to call home", now)

    def test_unmatched_text_is_not_treated_as_a_reminder(self):
        self.assertIsNone(parse_reminder_command("open notepad"))

    def test_reminders_persist_and_due_notifications_are_one_shot(self):
        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        item = self.store.add("take a break", due)
        reopened = ReminderStore(self.path)
        self.assertEqual(reopened.list()[0]["id"], item["id"])
        self.assertEqual(reopened.due()[0]["message"], "take a break")
        self.assertEqual(reopened.due(), [])

    def test_delete_reminder(self):
        item = self.store.add("test", datetime.now(timezone.utc) + timedelta(minutes=1))
        self.assertTrue(self.store.delete(item["id"]))
        self.assertFalse(self.store.delete(item["id"]))
        self.assertEqual(self.store.list(), [])

    def test_blank_and_oversized_messages_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add("   ", datetime.now(timezone.utc))
        with self.assertRaises(ValueError):
            self.store.add("x" * 301, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
