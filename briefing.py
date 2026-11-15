"""Read-only daily briefing for JARVIS: greeting, date/time, next reminders and PC health.

Pure functions (no database, no network, no side effects): the desktop app passes in the
reminders and the system snapshot it already has, so this is easy to test and cannot change
anything. Replies are Hinglish, matching the rest of JARVIS.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_PREFIX = re.compile(r"^(?:(?:hey\s+)?jarvis|please|zara|ek baar)(?=[,\s]|$)")
_COMMAND = re.compile(
    r"^(?:"
    r"(?:my\s+|mera\s+|meri\s+|daily\s+|morning\s+|day\s+)?briefing(?:\s+(?:do|dikhao|batao|sunao|please))?"
    r"|give me (?:a|my|the)\s+(?:daily\s+|morning\s+)?briefing"
    r"|(?:aaj\s+(?:ka|ki)|subah\s+(?:ka|ki))\s+(?:briefing|summary)(?:\s+(?:do|dikhao|batao|sunao))?"
    r"|(?:daily|morning)\s+summary"
    r"|good\s+morning(?:\s+jarvis)?|suprabhat(?:\s+jarvis)?"
    r")[\s?.!,]*$"
)


def is_briefing_command(prompt: str) -> bool:
    """True only for an explicit briefing request or a plain 'good morning'."""
    text = " ".join(str(prompt or "").casefold().split()).strip(" \t,;:.!?।॥")
    while _PREFIX.match(text):
        text = _PREFIX.sub("", text, count=1).strip(" \t,;:.!?।॥")
    return bool(_COMMAND.match(text))


def _greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Hello"


def _percent(text: str, label: str) -> float | None:
    match = re.search(rf"{label}[^\n:]*:\s*(\d+(?:\.\d+)?)%", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def pc_health_lines(system_text: str | None) -> list[str]:
    """Condense the PC snapshot into one summary line plus plain-language warnings."""
    if not system_text:
        return []
    cpu = _percent(system_text, "CPU usage")
    memory = _percent(system_text, "Memory usage")
    disk = _percent(system_text, "System drive usage")
    battery_match = re.search(r"Battery:\s*(\d+(?:\.\d+)?)%(\s*\(charging\))?", system_text, re.IGNORECASE)
    battery = float(battery_match.group(1)) if battery_match else None
    charging = bool(battery_match and battery_match.group(2))

    parts = []
    if cpu is not None:
        parts.append(f"CPU {cpu:.0f}%")
    if memory is not None:
        parts.append(f"RAM {memory:.0f}%")
    if disk is not None:
        parts.append(f"Drive {disk:.0f}%")
    if battery is not None:
        parts.append(f"Battery {battery:.0f}%" + (" (charging)" if charging else ""))
    lines = ["PC: " + ", ".join(parts) + "."] if parts else []

    if battery is not None and battery <= 20 and not charging:
        lines.append("Battery kam hai - charger laga lo.")
    if memory is not None and memory >= 85:
        lines.append("RAM kaafi bhari hui hai - zaroorat na ho to kuch apps band kar do.")
    if cpu is not None and cpu >= 90:
        lines.append("CPU bahut busy hai - 'top processes' bol ke dekh sakte ho kaun sa app le raha hai.")
    if disk is not None and disk >= 90:
        lines.append("System drive lagbhag full hai - purani files hata do.")
    return lines


def _reminder_line(item: dict, now: datetime) -> str | None:
    try:
        due = datetime.fromisoformat(str(item.get("due_at")))
    except (TypeError, ValueError):
        return None
    if due.tzinfo is None:
        due = due.astimezone()
    due = due.astimezone(now.tzinfo)
    when = due.strftime("%I:%M %p").lstrip("0")
    if due.date() == now.date():
        label = f"aaj {when}"
    elif due.date() == (now + timedelta(days=1)).date():
        label = f"kal {when}"
    else:
        label = f"{due.strftime('%d %b')} {when}"
    message = " ".join(str(item.get("message", "")).split())[:120]
    return f"- {label}: {message}" if message else None


def build_briefing(
    now: datetime,
    reminders: list[dict] | None = None,
    system_text: str | None = None,
    *,
    window_hours: int = 24,
    max_items: int = 5,
) -> str:
    """Compose the briefing text. ``now`` must be timezone-aware."""
    now = now if now.tzinfo else now.astimezone()
    lines = [
        f"{_greeting(now.hour)}! Aaj {now.strftime('%A, %d %B %Y')}, abhi {now.strftime('%I:%M %p').lstrip('0')} hue hain."
    ]

    horizon = now + timedelta(hours=window_hours)
    upcoming: list[tuple[datetime, str]] = []
    for item in reminders or []:
        if not isinstance(item, dict) or item.get("notified"):
            continue
        try:
            due = datetime.fromisoformat(str(item.get("due_at")))
        except (TypeError, ValueError):
            continue
        if due.tzinfo is None:
            due = due.astimezone()
        if now <= due <= horizon:
            line = _reminder_line(item, now)
            if line:
                upcoming.append((due, line))
    upcoming.sort(key=lambda pair: pair[0])
    if upcoming:
        lines.append(f"Agle {window_hours} ghante ke reminders ({len(upcoming)}):")
        lines.extend(line for _, line in upcoming[:max_items])
        if len(upcoming) > max_items:
            lines.append(f"...aur {len(upcoming) - max_items} aur.")
    else:
        lines.append(f"Agle {window_hours} ghante me koi reminder nahi hai.")

    lines.extend(pc_health_lines(system_text))
    return "\n".join(lines)
