"""Recoverable, exact-path file removal for trusted JARVIS UI workflows.

Only regular files inside the user's Desktop, Documents, or Downloads folders
are supported. Files are moved to the operating system trash/recycle bin;
permanent deletion is never used.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable


MAX_SELECTED_FILES = 20
ALLOWED_FOLDERS = ("Desktop", "Documents", "Downloads")


def validate_selected_files(paths: Iterable[str], *, home: Path | None = None) -> tuple[Path, ...]:
    if isinstance(paths, (str, bytes)):
        raise ValueError("Provide a list of exact file paths.")
    raw_paths = list(paths)
    if not raw_paths or len(raw_paths) > MAX_SELECTED_FILES:
        raise ValueError(f"Select between 1 and {MAX_SELECTED_FILES} files.")

    home_path = (home or Path.home()).resolve()
    roots = []
    for folder in ALLOWED_FOLDERS:
        candidate = home_path / folder
        if candidate.is_dir():
            roots.append(candidate.resolve())

    validated: list[Path] = []
    seen: set[str] = set()
    for raw in raw_paths:
        if not isinstance(raw, (str, os.PathLike)) or not str(raw).strip():
            raise ValueError("Every selected path must be explicit.")
        original = Path(raw).expanduser()
        # Reject symlinks before resolving so an in-root link cannot target outside.
        if original.is_symlink():
            raise ValueError("Symbolic links are not eligible for removal.")
        try:
            resolved = original.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("A selected file no longer exists or cannot be resolved.") from exc
        if not resolved.is_file():
            raise ValueError("Only individual regular files can be moved to the recycle bin.")
        if not any(resolved != root and root in resolved.parents for root in roots):
            raise ValueError("Files must be inside Desktop, Documents, or Downloads.")
        key = os.path.normcase(str(resolved))
        if key in seen:
            raise ValueError("Duplicate file selections are not allowed.")
        seen.add(key)
        validated.append(resolved)
    return tuple(validated)


def move_files_to_trash(
    paths: Iterable[str],
    *,
    consume_approval: Callable[[dict], object],
    home: Path | None = None,
    trash: Callable[[str], None] | None = None,
) -> tuple[str, ...]:
    """Consume a matching one-time approval, then move exact files to system trash."""
    files = validate_selected_files(paths, home=home)
    details = {"paths": [str(path) for path in files], "recovery": True}
    decision = consume_approval(details)
    if not getattr(decision, "approved", False):
        raise PermissionError("Exact file-removal approval is required; nothing was moved.")
    if trash is None:
        try:
            from send2trash import send2trash
        except ImportError as exc:
            raise RuntimeError(
                "Recoverable deletion is unavailable: install the Send2Trash dependency."
            ) from exc
        trash = send2trash

    moved: list[str] = []
    for path in files:
        # Never fall back to unlink/rmtree: a failed trash operation stops safely.
        trash(str(path))
        moved.append(str(path))
    return tuple(moved)
