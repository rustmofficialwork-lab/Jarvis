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
    r"\b(password|passphrase|passcode|pin|api[ _-]?key|access[ _-]?token|"
    r"secret|otp|one[ -]?time password|recovery code|private key|"
    r"credit card|debit card|cvv|cvc|bank account|routing number|"
    r"aadhaar|aadhar|pan number|passport number|social security number)\b",
    re.IGNORECASE,
)
_PAN_VALUE_PATTERN = re.compile(r"\b(?:PAN\s*[:#-]?\s*)[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR_VALUE_PATTERN = re.compile(
    r"\b(?:aadhaar|aadhar)\s*(?:number|no\.?)?\s*[:#-]?\s*(?:\d[ -]?){12}\b",
    re.IGNORECASE,
)
_CARD_VALUE_PATTERN = re.compile(
    r"\b(?:credit|debit)?\s*card\s*(?:number|no\.?)?\s*[:#-]?\s*((?:\d[ -]?){13,19})\b",
    re.IGNORECASE,
)
_BANK_ACCOUNT_PATTERN = re.compile(
    r"\b(?:bank\s+)?account\s*(?:number|no\.?)\s*[:#-]?\s*((?:\d[ -]?){8,18})\b",
    re.IGNORECASE,
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9\u0900-\u097f]+", re.IGNORECASE)
_MEMORY_STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does", "for",
    "from", "had", "has", "have", "he", "her", "here", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "me", "more", "most",
    "my", "no", "not", "of", "on", "or", "our", "out", "over", "please",
    "same", "she", "should", "so", "some", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "up", "us", "very", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "hai", "hain", "ho", "ka", "ki", "ko", "kya", "ke", "liye",
    "mein", "mera", "meri", "mere", "mujhe", "mujh", "par", "se", "aur",
    "kaise", "kab", "karo", "batao", "jarvis",
    # Common Devanagari Hindi stop words for multilingual memory retrieval.
    "और", "का", "की", "के", "को", "से", "में", "पर", "है", "हैं",
    "था", "थी", "थे", "यह", "वह", "ये", "वे", "इस", "उस", "एक",
    "मेरा", "मेरी", "मेरे", "मुझे", "आप", "आपका", "अपनी", "अपने",
    "क्या", "कैसे", "कब", "कहाँ", "क्यों", "बताओ", "करो", "करना",
    "मदद", "चाहिए", "लिए", "भी", "तो", "ही", "नहीं", "अब", "तक",
})


def _query_terms(query: str) -> list[str]:
    """Extract a small set of meaningful English/Hinglish terms for local retrieval."""
    return [
        term for term in _TOKEN_PATTERN.findall(str(query).casefold())
        if len(term) > 1 and term not in _MEMORY_STOP_WORDS
    ][:12]



def _has_luhn_valid_card_number(content: str) -> bool:
    """Detect labelled payment-card numbers without treating arbitrary digit strings as secrets."""
    for match in _CARD_VALUE_PATTERN.finditer(content):
        digits = re.sub(r"\D", "", match.group(1))
        total = 0
        parity = len(digits) % 2
        for index, char in enumerate(digits):
            number = int(char)
            if index % 2 == parity:
                number *= 2
                if number > 9:
                    number -= 9
            total += number
        if total % 10 == 0:
            return True
    return False


def _contains_sensitive_data(content: str) -> bool:
    return bool(
        _SECRET_PATTERN.search(content)
        or _PAN_VALUE_PATTERN.search(content)
        or _AADHAAR_VALUE_PATTERN.search(content)
        or _BANK_ACCOUNT_PATTERN.search(content)
        or _has_luhn_valid_card_number(content)
    )


class MemoryStore:
    """SQLite-backed user memories; never syncs them to the shared backend."""

    def __init__(self, path: Path = DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        self._memory_uri = None
        self._memory_anchor = None
        if str(self.path) == ":memory:":
            # Keep one connection alive: separate SQLite :memory: connections
            # otherwise see different databases and lose the schema immediately.
            self._memory_uri = f"file:jarvis_memory_{id(self)}?mode=memory&cache=shared"
            self._memory_anchor = sqlite3.connect(self._memory_uri, uri=True, timeout=10)
        else:
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
        db = sqlite3.connect(
            self._memory_uri or str(self.path),
            uri=self._memory_uri is not None,
            timeout=10,
        )
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
        if _contains_sensitive_data(content):
            raise ValueError(
                "JARVIS will not save passwords, PINs, account credentials, "
                "payment-card details, government ID numbers, or other secrets."
            )
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

    def context(
        self, limit: int = 12, max_chars: int = 3000, query: str | None = None
    ) -> list[str]:
        """Return a bounded memory slice, ranked by relevance when a prompt is supplied."""
        limit = max(1, min(int(limit), MAX_MEMORIES))
        max_chars = max(1, min(int(max_chars), 10_000))
        memories = self.list(MAX_MEMORIES)
        terms = _query_terms(query) if query else []
        if terms:
            ranked = []
            for item in memories:
                content_terms = set(_TOKEN_PATTERN.findall(
                    (item["content"] + " " + item["category"]).casefold()
                ))
                matched = content_terms.intersection(terms)
                if not matched:
                    continue
                score = len(matched)
                normalized_content = " ".join(item["content"].casefold().split())
                normalized_query = " ".join(str(query).casefold().split())
                if len(normalized_query) >= 4 and normalized_query in normalized_content:
                    score += 3
                ranked.append((score, item["updated_at"], item["id"], item["content"]))
            ranked.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
            candidates = [entry[3] for entry in ranked[:limit]]
        else:
            candidates = [item["content"] for item in memories[:limit]]

        selected = []
        used = 0
        for content in candidates:
            if used + len(content) > max_chars:
                continue
            selected.append(content)
            used += len(content)
        return selected
