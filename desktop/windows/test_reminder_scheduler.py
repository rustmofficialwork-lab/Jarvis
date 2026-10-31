import subprocess
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from reminder_scheduler import (
    build_create_task_command,
    notify_due_reminders,
    register_reminder_task,
    remove_all_reminder_tasks,
    sync_pending_reminder_tasks,
    unregister_reminder_task,
)


class FakeStore:
    def __init__(self, items):
        self.items = items
        self.claimed = []

    def due(self):
        due, self.items = self.items, []
        self.claimed.extend(due)
        return due

    def list(self):
        return self.items

    def release_claims(self, reminder_ids):
        self.released = list(reminder_ids)


class ReminderSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        self.item = {
            "id": 7, "message": "drink water",
            "due_at": (self.now + timedelta(minutes=5, seconds=1)).isoformat(),
            "notified": 0,
        }

    def test_task_is_rounded_up_to_next_minute_and_user_interactive(self):
        command = build_create_task_command(
            self.item, executable=r"C:\Program Files\JARVIS\JARVIS.exe",
            frozen=True, now=self.now,
        )
        self.assertEqual(command[0:4], ["schtasks.exe", "/Create", "/SC", "ONCE"])
        self.assertEqual(command[5], "10/31/2026")
        self.assertEqual(command[7], "12:06")
        self.assertIn("/IT", command)
        self.assertIn("/RL", command)
        self.assertEqual(command[command.index("/TN") + 1], "JARVIS_Reminder_7")
        self.assertIn("--reminder-check", command[command.index("/TR") + 1])

    def test_task_command_uses_pythonw_for_source_run(self):
        with tempfile.TemporaryDirectory() as folder:
            python_exe = Path(folder) / "python.exe"
            pythonw_exe = Path(folder) / "pythonw.exe"
            python_exe.touch()
            pythonw_exe.touch()
            command = build_create_task_command(
                self.item, executable=str(python_exe),
                script_path=r"C:\\JARVIS\\jarvis_desktop.py", frozen=False,
                now=self.now,
            )
        action = command[command.index("/TR") + 1]
        self.assertIn("pythonw.exe", action)
        self.assertIn("jarvis_desktop.py", action)
        self.assertIn("--reminder-check", action)

    def test_register_and_unregister_use_schtasks_without_shell(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "", "")

        self.assertTrue(register_reminder_task(
            self.item, platform_name="nt", runner=runner, frozen=True, now=self.now
        ))
        self.assertTrue(unregister_reminder_task(
            7, platform_name="nt", runner=runner
        ))
        self.assertEqual(calls[0][0][1], "/Create")
        self.assertEqual(calls[1][0], ["schtasks.exe", "/Delete", "/TN", "JARVIS_Reminder_7", "/F"])
        self.assertNotIn("shell", calls[0][1])

    def test_non_windows_does_not_register_tasks_or_show_dialogs(self):
        self.assertFalse(register_reminder_task(self.item, platform_name="posix"))
        self.assertFalse(unregister_reminder_task(7, platform_name="posix"))
        self.assertEqual(notify_due_reminders(FakeStore([self.item]), platform_name="posix"), 0)

    def test_notification_claims_due_items_and_removes_their_tasks(self):
        store = FakeStore([self.item])
        messages = []
        removed = []

        # Patch task removal at module scope to keep this test independent of Windows.
        import reminder_scheduler
        original = reminder_scheduler.unregister_reminder_task
        reminder_scheduler.unregister_reminder_task = lambda reminder_id, **kwargs: removed.append(reminder_id)
        try:
            count = notify_due_reminders(
                store, notifier=messages.append, platform_name="nt"
            )
        finally:
            reminder_scheduler.unregister_reminder_task = original

        self.assertEqual(count, 1)
        self.assertEqual(messages, ["Reminder: drink water"])
        self.assertEqual(removed, [7])


    def test_notification_failure_releases_current_and_remaining_reminders(self):
        second = {**self.item, "id": 8, "message": "take a break"}
        store = FakeStore([self.item, second])
        store.released = []
        removed = []

        import reminder_scheduler
        original = reminder_scheduler.unregister_reminder_task
        reminder_scheduler.unregister_reminder_task = (
            lambda reminder_id, **kwargs: removed.append(reminder_id)
        )
        try:
            with self.assertRaisesRegex(RuntimeError, "dialog failed"):
                notify_due_reminders(
                    store,
                    notifier=lambda _message: (_ for _ in ()).throw(RuntimeError("dialog failed")),
                    platform_name="nt",
                )
        finally:
            reminder_scheduler.unregister_reminder_task = original

        self.assertEqual(store.released, [7, 8])
        self.assertEqual(removed, [])

    def test_task_cleanup_failure_does_not_skip_later_notifications(self):
        second = {**self.item, "id": 8, "message": "take a break"}
        store = FakeStore([self.item, second])
        messages = []

        import reminder_scheduler
        original = reminder_scheduler.unregister_reminder_task
        reminder_scheduler.unregister_reminder_task = (
            lambda reminder_id, **kwargs: (_ for _ in ()).throw(OSError("scheduler unavailable"))
        )
        try:
            count = notify_due_reminders(
                store, notifier=messages.append, platform_name="nt"
            )
        finally:
            reminder_scheduler.unregister_reminder_task = original

        self.assertEqual(count, 2)
        self.assertEqual(messages, ["Reminder: drink water", "Reminder: take a break"])

    def test_uninstall_cleanup_removes_tasks_for_saved_reminders(self):
        store = FakeStore([self.item, {**self.item, "id": 8}])
        removed = []
        import reminder_scheduler
        original = reminder_scheduler.unregister_reminder_task
        reminder_scheduler.unregister_reminder_task = (
            lambda reminder_id, **kwargs: removed.append(reminder_id) or True
        )
        try:
            count, errors = remove_all_reminder_tasks(store, platform_name="nt")
        finally:
            reminder_scheduler.unregister_reminder_task = original
        self.assertEqual(count, 2)
        self.assertEqual(errors, [])
        self.assertEqual(removed, [7, 8])

    def test_startup_sync_repairs_only_pending_reminders(self):
        items = [self.item, {**self.item, "id": 8, "notified": 1}]
        store = FakeStore(items)
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        created, errors = sync_pending_reminder_tasks(
            store, platform_name="nt", runner=runner, frozen=True, now=self.now
        )
        self.assertEqual(created, 1)
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 1)
        self.assertIn("JARVIS_Reminder_7", calls[0])


if __name__ == "__main__":
    unittest.main()
