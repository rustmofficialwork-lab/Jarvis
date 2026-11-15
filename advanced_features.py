"""Local focus sessions and allowlisted recurring workflow automation."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import os

DEFAULT_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JARVISDesktop" / "advanced_features.sqlite3"
WORKFLOWS = {
    "study": ("Study setup", ("open notepad", "open calculator")),
    "meeting": ("Meeting setup", ("open browser", "open notepad")),
    "deep_work": ("Deep work setup", ("open notepad", "open task manager")),
}
MAX_INTERVAL_MINUTES = 10080


@contextmanager
def _db(path, uri=False):
    db = sqlite3.connect(str(path), uri=uri, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


class AdvancedFeatureStore:
    """Persistent local-only state for focus sessions and recurring allowlisted workflows."""

    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self._db_uri = str(self.path) == ":memory:"
        self._db_path = (
            f"file:jarvis_advanced_{id(self)}?mode=memory&cache=shared"
            if self._db_uri else str(self.path)
        )
        self._memory_anchor = (
            sqlite3.connect(self._db_path, uri=True, timeout=10)
            if self._db_uri else None
        )
        if not self._db_uri:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with _db(self._db_path, uri=self._db_uri) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS focus_session (
                id INTEGER PRIMARY KEY CHECK(id=1), started_at TEXT NOT NULL,
                ends_at TEXT NOT NULL, duration_minutes INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS automations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workflow TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL, next_run TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1)""")

    def start_focus(self, minutes=25, now=None):
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 240:
            raise ValueError("Focus duration 1 se 240 minutes ke beech honi chahiye.")
        now = (now or datetime.now().astimezone()).astimezone()
        end = now + timedelta(minutes=minutes)
        with _db(self._db_path, uri=self._db_uri) as db:
            db.execute("INSERT OR REPLACE INTO focus_session(id,started_at,ends_at,duration_minutes) VALUES(1,?,?,?)",
                       (now.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), minutes))
        return end

    def stop_focus(self):
        with _db(self._db_path, uri=self._db_uri) as db:
            return db.execute("DELETE FROM focus_session WHERE id=1").rowcount > 0

    def focus_status(self, now=None):
        now = (now or datetime.now().astimezone()).astimezone()
        with _db(self._db_path, uri=self._db_uri) as db:
            row = db.execute("SELECT * FROM focus_session WHERE id=1").fetchone()
            if row is None:
                return None
            end = datetime.fromisoformat(row["ends_at"])
            if end <= now:
                db.execute("DELETE FROM focus_session WHERE id=1")
                return {"expired": True, "duration_minutes": row["duration_minutes"]}
            remaining = max(0, int((end-now).total_seconds()+59)//60)
            return {"expired": False, "remaining_minutes": remaining,
                    "ends_at": end, "duration_minutes": row["duration_minutes"]}

    def add_automation(self, workflow, interval_minutes, now=None):
        if workflow not in WORKFLOWS:
            raise ValueError("Workflow allowlist mein nahi hai. study, meeting ya deep_work use karo.")
        if isinstance(interval_minutes, bool) or not isinstance(interval_minutes, int) or not 5 <= interval_minutes <= MAX_INTERVAL_MINUTES:
            raise ValueError("Repeat interval 5 minutes se 7 days ke beech rakho.")
        now = (now or datetime.now().astimezone()).astimezone()
        next_run = now + timedelta(minutes=interval_minutes)
        with _db(self._db_path, uri=self._db_uri) as db:
            cur = db.execute("INSERT INTO automations(workflow,interval_minutes,next_run) VALUES(?,?,?)",
                             (workflow, interval_minutes, next_run.isoformat(timespec="seconds")))
            return cur.lastrowid, next_run

    def list_automations(self):
        with _db(self._db_path, uri=self._db_uri) as db:
            return [dict(row) for row in db.execute("SELECT * FROM automations WHERE enabled=1 ORDER BY id")]

    def delete_automation(self, automation_id):
        with _db(self._db_path, uri=self._db_uri) as db:
            return db.execute("DELETE FROM automations WHERE id=?", (int(automation_id),)).rowcount > 0

    def claim_due_automations(self, now=None):
        now = (now or datetime.now().astimezone()).astimezone()
        now_text = now.isoformat(timespec="seconds")
        claimed = []
        with _db(self._db_path, uri=self._db_uri) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM automations WHERE enabled=1 AND julianday(next_run)<=julianday(?) ORDER BY id",
                              (now_text,)).fetchall()
            for row in rows:
                next_run = now + timedelta(minutes=row["interval_minutes"])
                db.execute("UPDATE automations SET next_run=? WHERE id=?",
                           (next_run.isoformat(timespec="seconds"), row["id"]))
                claimed.append(dict(row))
        return claimed

    def retry_automation(self, automation_id, now=None):
        """Retry a failed workflow after five minutes instead of silently skipping its cycle."""
        now = (now or datetime.now().astimezone()).astimezone()
        retry_at = now + timedelta(minutes=5)
        with _db(self._db_path, uri=self._db_uri) as db:
            cursor = db.execute(
                "UPDATE automations SET next_run=? WHERE id=? AND enabled=1",
                (retry_at.isoformat(timespec="seconds"), int(automation_id)),
            )
        return retry_at if cursor.rowcount else None


def parse_advanced_command(prompt):
    text = " ".join(str(prompt).strip().split())
    lower = text.casefold().strip(" .!?।")
    if lower in {"stop focus", "end focus", "focus band karo", "pomodoro stop"}:
        return ("focus_stop", None)
    if lower in {"focus status", "pomodoro status", "mera focus status"}:
        return ("focus_status", None)
    if lower in {"start pomodoro", "start focus", "focus mode"}:
        return ("focus_start", 25)
    match = re.fullmatch(r"(?:start focus|focus mode|start pomodoro) for (\d{1,3}) minutes?", lower)
    if match:
        return ("focus_start", int(match.group(1)))
    match = re.fullmatch(r"(?:run|start) (study|meeting|deep work) (?:workflow|setup)", lower)
    if match:
        return ("workflow", "deep_work" if match.group(1) == "deep work" else match.group(1))
    match = re.fullmatch(r"(?:repeat|schedule) (study|meeting|deep work) (?:workflow|setup) every (\d{1,5}) minutes?", lower)
    if match:
        return ("automation_add", ("deep_work" if match.group(1) == "deep work" else match.group(1), int(match.group(2))))
    if lower in {"list automations", "show automations", "my automations"}:
        return ("automation_list", None)
    match = re.fullmatch(r"(?:delete|remove|stop) automation (\d+)", lower)
    if match:
        return ("automation_delete", int(match.group(1)))
    return None
