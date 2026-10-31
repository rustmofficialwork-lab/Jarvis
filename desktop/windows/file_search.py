"""Safe, bounded filename search inside a folder explicitly chosen by the user."""
from __future__ import annotations

import os
from pathlib import Path

MAX_RESULTS = 50
MAX_DIRECTORIES = 5000
SAFE_OPEN_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".log", ".ini",
    ".yaml", ".yml", ".xml", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".webp", ".mp3", ".wav", ".mp4", ".m4a", ".flac",
}


def parse_open_result_index(prompt: str) -> int | None:
    """Parse an explicit numbered result selection from English/Hinglish."""
    import re

    normalized = " ".join(str(prompt).casefold().strip().rstrip(" .!?।॥").split())
    match = re.fullmatch(
        r"(?:open file|open result|file kholo|result kholo|फाइल खोलो)\s+(\d{1,2})",
        normalized,
    )
    if not match:
        return None
    index = int(match.group(1))
    return index if 1 <= index <= 50 else None


def validate_search_result_for_open(path: str | os.PathLike) -> Path:
    """Validate a selected search result as a regular, non-link, passive file."""
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or candidate.suffix.casefold() not in SAFE_OPEN_EXTENSIONS:
        raise ValueError("For safety, JARVIS opens only supported document and media file types.")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("The selected search result is no longer a regular file.")
    return resolved


def parse_file_search_query(prompt: str) -> str | None:
    """Extract a filename fragment from supported English/Hinglish commands."""
    normalized = " ".join(str(prompt).casefold().strip().rstrip(" .!?।॥").split())
    prefixes = (
        "find file ", "search file ", "find files ", "search files ",
        "file dhundo ", "file khojo ", "file dhoondo ",
        "फाइल ढूंढो ", "फाइल खोजो ",
    )
    for prefix in prefixes:
        if normalized.startswith(prefix):
            query = normalized[len(prefix):].strip()
            if query and len(query) <= 120 and not any(ch in query for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|")):
                return query
            return None
    return None


def search_files(root: str | os.PathLike, query: str, *,
                 max_results: int = MAX_RESULTS,
                 max_directories: int = MAX_DIRECTORIES) -> list[str]:
    """Search names only; never follows symlinks or reads file contents."""
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    needle = str(query).strip().casefold()
    if not needle or len(needle) > 120 or any(ch in needle for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|")):
        raise ValueError("Enter a simple filename or extension, not a path or wildcard.")
    if not 1 <= max_results <= 200 or not 1 <= max_directories <= 20000:
        raise ValueError("Search limits are outside the supported range.")

    matches: list[str] = []
    visited = 0
    for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
        visited += 1
        if visited > max_directories:
            break
        current_path = Path(current)
        safe_dirs = []
        for name in dirs:
            candidate = current_path / name
            try:
                if name.startswith(".") or candidate.is_symlink():
                    continue
                attrs = getattr(candidate.stat(follow_symlinks=False), "st_file_attributes", 0)
                if attrs & 0x2:  # Windows FILE_ATTRIBUTE_HIDDEN
                    continue
                safe_dirs.append(name)
            except OSError:
                continue
        dirs[:] = safe_dirs
        for name in files:
            if name.startswith(".") or needle not in name.casefold():
                continue
            candidate = current_path / name
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                attrs = getattr(candidate.stat(follow_symlinks=False), "st_file_attributes", 0)
                if attrs & 0x2:
                    continue
                matches.append(str(candidate))
            except OSError:
                continue
            if len(matches) >= max_results:
                return matches
    return matches
