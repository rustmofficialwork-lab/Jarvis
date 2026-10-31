"""Persistent local reminders for the Windows JARVIS desktop app."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import os

DEFAULT_REMINDER_PATH = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) /
    "JARVISDesktop" / "reminders.sqlite3"
)
MAX_REMINDER_LENGTH = 300


@contextmanager
def _connection(path: Path):
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


class ReminderStore:
    """Small SQLite queue; reminders remain on this PC and work offline."""

    def __init__(self, path: Path = DEFAULT_REMINDER_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _connection(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                due_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notified INTEGER NOT NULL DEFAULT 0
            )""")

    def add(self, message: str, due_at: datetime) -> dict:
        message = " ".join(str(message).strip().split())
        if not message:
            raise ValueError("Reminder ka message khaali nahi ho sakta.")
        if len(message) > MAX_REMINDER_LENGTH:
            raise ValueError(f"Reminder {MAX_REMINDER_LENGTH} characters se chhota rakho.")
        if due_at.tzinfo is None:
            due_at = due_at.astimezone()
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with _connection(self.path) as db:
            cur = db.execute(
                "INSERT INTO reminders(message,due_at,created_at) VALUES(?,?,?)",
                (message, due_at.astimezone().isoformat(timespec="seconds"), now),
            )
            row = db.execute("SELECT * FROM reminders WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def list(self, limit: int = 100) -> list[dict]:
        with _connection(self.path) as db:
            rows = db.execute(
                "SELECT * FROM reminders ORDER BY julianday(due_at) LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        return [dict(row) for row in rows]

    def due(self, now: datetime | None = None) -> list[dict]:
        now = (now or datetime.now().astimezone()).astimezone().isoformat(timespec="seconds")
        with _connection(self.path) as db:
            # Acquire the write lock before selecting so the desktop poller and
            # Task Scheduler helper cannot both claim and display the same item.
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM reminders WHERE notified=0 AND julianday(due_at)<=julianday(?) ORDER BY julianday(due_at)",
                (now,),
            ).fetchall()
            if rows:
                db.executemany(
                    "UPDATE reminders SET notified=1 WHERE id=?",
                    [(row["id"],) for row in rows],
                )
        return [dict(row) for row in rows]

    def release_claims(self, reminder_ids: list[int]) -> None:
        """Return unshown reminders to the pending queue after notification failure."""
        ids = [int(reminder_id) for reminder_id in reminder_ids]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with _connection(self.path) as db:
            db.execute(
                f"UPDATE reminders SET notified=0 WHERE id IN ({placeholders})",
                ids,
            )

    def delete(self, reminder_id: int) -> bool:
        with _connection(self.path) as db:
            cur = db.execute("DELETE FROM reminders WHERE id=?", (int(reminder_id),))
            return cur.rowcount > 0


def parse_reminder_command(text: str, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Parse safe, explicit English/Hinglish reminder phrases; return None if unmatched."""
    now = now or datetime.now().astimezone()
    text = " ".join(text.strip().split())
    patterns = [
        (r"^(?:remind me|reminder) in (\d+) (seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|second|minute|ghante?|ghanta|din) to (.+)$", "relative"),
        (r"^(?:mujhe )?(\d+) (seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|second|minute|ghante?|ghanta|din) baad (.+?)(?: yaad dilana| yaad dila dena)$", "relative_hi"),
        (r"^(?:remind me|set a reminder) at (\d{1,2}):(\d{2}) to (.+)$", "clock"),
        (r"^(\d{1,2}):(\d{2}) par (.+?)(?: ke liye )?reminder laga do$", "clock_hi"),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if not match:
            continue
        groups = match.groups()
        if kind.startswith("relative"):
            amount = int(groups[0])
            unit = groups[1].casefold()
            message = groups[2] if kind == "relative_hi" else groups[2]
            if amount < 1 or amount > 365:
                raise ValueError("Reminder ka time 1 se 365 units ke beech rakho.")
            if unit.startswith(("sec",)):
                delta = timedelta(seconds=amount)
            elif unit.startswith(("min",)):
                delta = timedelta(minutes=amount)
            elif unit.startswith(("hour", "hr", "ghant")):
                delta = timedelta(hours=amount)
            elif unit.startswith("din"):
                delta = timedelta(days=amount)
            else:
                delta = timedelta(days=amount)
            return message.strip(" .!?।"), now + delta
        hour, minute, message = int(groups[0]), int(groups[1]), groups[2]
        if hour > 23 or minute > 59:
            raise ValueError("Time 24-hour format mein do, jaise 18:30.")
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
        return message.strip(" .!?।"), due
    return None
