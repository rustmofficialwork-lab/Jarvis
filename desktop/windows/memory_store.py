"""Private, offline-first memory store for the Windows JARVIS desktop app."""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MEMORY_PATH = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) /
    "JARVISDesktop" / "memory.sqlite3"
)
MAX_MEMORIES = 500
MAX_CONTENT_LENGTH = 500
_SECRET_PATTERN = re.compile(
    r"\b(password|passcode|api[ _-]?key|access[ _-]?token|secret|otp|"
    r"recovery code|private key)\b",
    re.IGNORECASE,
)


class MemoryStore:
    """SQLite-backed user memories; never syncs them to the shared backend."""

    def __init__(self, path: Path = DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_content "
                "ON memories(content COLLATE NOCASE)"
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def validate(content: str) -> str:
        if not isinstance(content, str):
            raise ValueError("Memory must be text.")
        content = " ".join(content.strip().split())
        if not content:
            raise ValueError("Memory cannot be empty.")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Memory must be {MAX_CONTENT_LENGTH} characters or fewer.")
        if _SECRET_PATTERN.search(content):
            raise ValueError("JARVIS will not save passwords, API keys, tokens, OTPs, or secrets.")
        return content

    def add(self, content: str, category: str = "general") -> dict:
        content = self.validate(content)
        category = " ".join(str(category).strip().split())[:40] or "general"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            existing = db.execute(
                "SELECT * FROM memories WHERE content = ? COLLATE NOCASE",
                (content,),
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE memories SET category=?, updated_at=? WHERE id=?",
                    (category, now, existing["id"]),
                )
                row_id = existing["id"]
            else:
                if count >= MAX_MEMORIES:
                    raise ValueError("Memory is full. Delete an old memory before adding another.")
                cursor = db.execute(
                    "INSERT INTO memories(content, category, created_at, updated_at) VALUES(?,?,?,?)",
                    (content, category, now, now),
                )
                row_id = cursor.lastrowid
            row = db.execute("SELECT * FROM memories WHERE id=?", (row_id,)).fetchone()
        return dict(row)

    def list(self, limit: int = MAX_MEMORIES) -> list[dict]:
        limit = max(1, min(int(limit), MAX_MEMORIES))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        query = " ".join(str(query).casefold().split())
        if not query:
            return self.list(limit)
        terms = [term for term in query.split() if len(term) > 1][:8]
        if not terms:
            return []
        where = " AND ".join("content LIKE ?" for _ in terms)
        params = [f"%{term}%" for term in terms]
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM memories WHERE {where} ORDER BY updated_at DESC LIMIT ?",
                (*params, max(1, min(int(limit), 100))),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, memory_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM memories WHERE id=?", (int(memory_id),))
        return cursor.rowcount > 0

    def update(self, memory_id: int, content: str, category: str = "general") -> dict:
        content = self.validate(content)
        category = " ".join(str(category).strip().split())[:40] or "general"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            try:
                cursor = db.execute(
                    "UPDATE memories SET content=?, category=?, updated_at=? WHERE id=?",
                    (content, category, now, int(memory_id)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("That memory already exists.") from exc
            if not cursor.rowcount:
                raise KeyError("Memory not found.")
            row = db.execute("SELECT * FROM memories WHERE id=?", (int(memory_id),)).fetchone()
        return dict(row)

    def clear(self) -> int:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM memories")
        return cursor.rowcount

    def context(self, limit: int = 12, max_chars: int = 3000) -> list[str]:
        """Return a small, newest-first memory slice for the local chat request."""
        selected = []
        used = 0
        for item in self.list(limit):
            content = item["content"]
            if used + len(content) > max_chars:
                continue
            selected.append(content)
            used += len(content)
        return selected
