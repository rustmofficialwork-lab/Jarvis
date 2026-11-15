"""Multi-step commands for JARVIS: "notepad kholo aur phir calculator kholo".

A chain is split into clauses, and it runs only when EVERY clause is already one of the
fixed, allowlisted local actions. The caller first validates all clauses with a dry run
(no side effects), so a chain never half-executes because of a typo in step 3.
Nothing here widens what JARVIS may do: each step still goes through the same allowlist.
"""
from __future__ import annotations

import re
from typing import Callable

MAX_CHAIN_STEPS = 4

# Longest connectors first so "and then" is not split as "and" + "then".
_CONNECTORS = (
    r"and then|and after that|after that|then|aur phir|aur fir|phir se|phir|fir|uske baad|uske bad|"
    r"और फिर|उसके बाद|फिर|and|aur|और|plus"
)
_SPLIT = re.compile(rf"\s*(?:[;,]\s*)?(?<![\w])(?:{_CONNECTORS})(?![\w])\s*|\s*[;,]\s*", re.IGNORECASE)


def split_chain(prompt: str) -> list[str]:
    """Split a spoken/typed request into clauses; a plain command comes back as one clause."""
    text = " ".join(str(prompt or "").split())
    if not text:
        return []
    parts = [part.strip(" \t\r\n,;:.!?।॥") for part in _SPLIT.split(text)]
    parts = [part for part in parts if part]
    return parts or [text]


def run_chain(
    prompt: str,
    run_single: Callable[..., str | None],
    *,
    max_steps: int = MAX_CHAIN_STEPS,
) -> str | None:
    """Run ``prompt`` as a chain of allowlisted commands, or return None if it is not one.

    ``run_single(command, dry_run=bool)`` must return a string for a recognised command and
    None for anything else. All clauses are validated first; only then is anything executed.
    """
    clauses = split_chain(prompt)
    if len(clauses) < 2 or len(clauses) > max_steps:
        return None
    for clause in clauses:
        if run_single(clause, dry_run=True) is None:
            return None
    results: list[str] = []
    for index, clause in enumerate(clauses, start=1):
        try:
            result = run_single(clause, dry_run=False)
        except Exception as exc:
            done = f"{len(results)} step(s) completed" if results else "nothing was run yet"
            raise RuntimeError(f"Step {index} ('{clause}') failed ({done}): {exc}") from exc
        results.append(str(result).strip())
    return f"Done - {len(clauses)} steps. " + " ".join(results)
