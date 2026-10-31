"""Windows Task Scheduler integration for reminders.

Each pending reminder gets a one-shot, current-user task. The task launches
JARVIS in a lightweight notification-only mode, so reminders can fire while
the main app is closed (the user must be signed in; the PC must be awake).
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

TASK_PREFIX = "JARVIS_Reminder_"


def _task_name(reminder_id: int) -> str:
    return TASK_PREFIX + str(int(reminder_id))


def _command_parts(executable=None, script_path=None, frozen=None) -> list[str]:
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    app_executable = str(executable or sys.executable)
    if is_frozen:
        return [app_executable, "--reminder-check"]
    executable_path = Path(app_executable)
    pythonw = executable_path.with_name("pythonw.exe")
    runner = str(pythonw if pythonw.exists() else executable_path)
    return [runner, str(script_path or Path(__file__).with_name("jarvis_desktop.py")),
            "--reminder-check"]


def build_create_task_command(reminder: dict, executable=None, script_path=None,
                              frozen=None, now: datetime | None = None) -> list[str]:
    """Build a one-shot interactive task, rounded up to Task Scheduler's minute precision."""
    due = datetime.fromisoformat(str(reminder["due_at"]))
    if due.tzinfo is None:
        due = due.astimezone()
    due = due.astimezone()
    scheduled = due.replace(second=0, microsecond=0)
    if scheduled < due:
        scheduled += timedelta(minutes=1)
    current = (now or datetime.now().astimezone()).astimezone()
    if scheduled <= current:
        scheduled = current.replace(second=0, microsecond=0) + timedelta(minutes=1)

    action = subprocess.list2cmdline(
        _command_parts(executable, script_path, frozen)
    )
    return [
        "schtasks.exe", "/Create", "/SC", "ONCE",
        "/SD", scheduled.strftime("%m/%d/%Y"),
        "/ST", scheduled.strftime("%H:%M"),
        "/TN", _task_name(reminder["id"]),
        "/TR", action, "/F", "/IT", "/RL", "LIMITED",
    ]


def register_reminder_task(reminder: dict, executable=None, script_path=None,
                           frozen=None, platform_name=None, runner=None,
                           now: datetime | None = None) -> bool:
    """Register a per-user one-shot task; never requests elevation or a password."""
    if (platform_name or os.name) != "nt":
        return False
    run = runner or subprocess.run
    kwargs = {"check": True, "capture_output": True, "text": True, "timeout": 20}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    run(build_create_task_command(reminder, executable, script_path, frozen, now), **kwargs)
    return True


def unregister_reminder_task(reminder_id: int, platform_name=None, runner=None) -> bool:
    """Remove the scheduled task for one reminder; a missing task is harmless."""
    if (platform_name or os.name) != "nt":
        return False
    run = runner or subprocess.run
    kwargs = {"capture_output": True, "text": True, "timeout": 20}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    result = run(["schtasks.exe", "/Delete", "/TN", _task_name(reminder_id), "/F"],
                 check=False, **kwargs)
    # schtasks reports a missing task as non-zero; deletion remains idempotent.
    return getattr(result, "returncode", 0) == 0


def notify_due_reminders(store=None, notifier=None, platform_name=None) -> int:
    """Claim due reminders and release unshown items if a notification fails."""
    if (platform_name or os.name) != "nt":
        return 0
    if store is None:
        from reminders import ReminderStore
        store = ReminderStore()
    if notifier is None:
        import ctypes
        notifier = lambda message: ctypes.windll.user32.MessageBoxW(
            0, message, "JARVIS Reminder", 0x40 | 0x1000
        )
    due_items = store.due()
    for index, item in enumerate(due_items):
        try:
            notifier("Reminder: " + str(item["message"]))
        except Exception:
            # due() claims the whole batch atomically. Release this and all
            # remaining items so a failed dialog cannot silently lose reminders.
            store.release_claims([pending["id"] for pending in due_items[index:]])
            raise
        unregister_reminder_task(item["id"], platform_name=platform_name)
    return len(due_items)


def sync_pending_reminder_tasks(store=None, **kwargs) -> tuple[int, list[str]]:
    """Repair missing one-shot tasks on app startup without failing app launch."""
    if store is None:
        from reminders import ReminderStore
        store = ReminderStore()
    created = 0
    errors = []
    for item in store.list():
        if item.get("notified"):
            continue
        try:
            if register_reminder_task(item, **kwargs):
                created += 1
        except Exception as exc:
            errors.append(f"Reminder #{item['id']}: {exc}")
    return created, errors

def remove_all_reminder_tasks(store=None, platform_name=None) -> tuple[int, list[str]]:
    """Remove all reminder tasks before uninstall, preserving the local reminder DB."""
    if (platform_name or os.name) != "nt":
        return 0, []
    if store is None:
        from reminders import ReminderStore
        store = ReminderStore()
    removed = 0
    errors = []
    for item in store.list():
        try:
            if unregister_reminder_task(item["id"], platform_name=platform_name):
                removed += 1
        except Exception as exc:
            errors.append(f"Reminder #{item['id']}: {exc}")
    return removed, errors
