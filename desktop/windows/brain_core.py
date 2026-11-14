"""JARVIS AI brain policy core.

This module is deliberately deterministic: the model may suggest a tool call,
but only this policy layer decides whether that call is allowed to run.
No model-generated shell commands, code, paths, or arbitrary URLs are executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    status: str
    reason: str


READ_ONLY_TOOLS = frozenset({
    "calculator",
    "get_local_time",
    "get_system_status",
    "get_top_processes",
    "get_available_capabilities",
    "list_user_files",
    "search_user_files",
    "read_user_text_file",
})
USER_DIRECTED_TOOLS = frozenset({"open_app", "open_website"})
# Exact domain aliases prevent deceptive hosts such as youtube.com.attacker.invalid.
SITE_ALIASES = {"youtube": "youtube.com", "google": "google.com", "github": "github.com", "gmail": "mail.google.com", "wikipedia": "wikipedia.org", "reddit": "reddit.com", "stackoverflow": "stackoverflow.com"}
SENSITIVE_TOOL_NAMES = frozenset({
    "send_money", "make_payment", "purchase_item", "send_email",
    "send_message", "delete_file", "delete_folder", "change_account",
    "change_security_settings", "run_shell_command", "execute_script",
})
SUPPORTED_MODES = frozenset({"auto", "online", "offline"})


def choose_mode(
    preference: str,
    *,
    internet_available: bool,
    local_model_available: bool,
) -> str:
    """Choose an available AI route without claiming an unavailable route works."""
    selected = str(preference or "auto").strip().casefold()
    if selected not in SUPPORTED_MODES:
        selected = "auto"
    if selected == "online":
        return "online" if internet_available else "unavailable"
    if selected == "offline":
        return "offline" if local_model_available else "unavailable"
    if internet_available and local_model_available:
        return "hybrid"
    if internet_available:
        return "online"
    if local_model_available:
        return "offline"
    return "unavailable"


def _explicit_action(prompt: str) -> bool:
    text = str(prompt or "").strip().casefold()
    if re.search(
        r"\b(don't|do not|never|avoid|mat|nahi|nahin)\b.{0,40}\b(open|launch|start|visit|go to|kholo|khol|chalao)\b",
        text,
    ):
        return False
    direct = re.search(
        r"^\s*(?:(?:please|hey jarvis|jarvis|can you|could you|would you|zara|i want you to)\s+)*(?:open|launch|start|visit|go to|kholo|khol do|chalao|shuru karo)\b",
        text,
    )
    hinglish = re.search(
        r"\b(notepad|calculator|calc|paint|file explorer|explorer|task manager|youtube|google)\s+(?:kholo|khol do|chalao)\b",
        text,
    )
    return bool(direct or hinglish)


def authorize_tool_call(
    name: str,
    arguments: dict[str, Any],
    user_prompt: str,
) -> ToolDecision:
    """Authorize model-suggested calls against the user's actual request.

    Read-only tools are allowed within their own argument validators.
    App/browser navigation must be directly requested by the user.
    Sensitive or unknown tools are denied; a model response is never consent.
    """
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return ToolDecision(False, "invalid", "Malformed tool request.")
    tool = name.strip().casefold()
    if tool in SENSITIVE_TOOL_NAMES:
        return ToolDecision(
            False, "confirmation_required",
            "This action is sensitive and is not enabled as an automatic AI tool. "
            "A separate trusted confirmation flow and dedicated integration are required.",
        )
    if tool in READ_ONLY_TOOLS:
        return ToolDecision(True, "allowed", "Read-only tool is within the local allowlist.")
    if tool not in USER_DIRECTED_TOOLS:
        return ToolDecision(False, "unsupported", "This tool is not in JARVIS's approved capability registry.")
    if not _explicit_action(user_prompt):
        return ToolDecision(False, "not_requested", "The user did not directly request this action.")

    if tool == "open_app":
        app = arguments.get("app")
        aliases = {
            "notepad": ("notepad",),
            "calculator": ("calculator", "calc"),
            "paint": ("paint",),
            "file_explorer": ("file explorer", "explorer"),
            "task_manager": ("task manager",),
        }
        expected = aliases.get(app) if isinstance(app, str) else None
        prompt = str(user_prompt).casefold()
        if not expected or not any(alias in prompt for alias in expected):
            return ToolDecision(False, "not_requested", "The requested app was not named by the user.")
        return ToolDecision(True, "allowed", "The user explicitly requested this allowlisted app.")

    url = arguments.get("url")
    if not isinstance(url, str):
        return ToolDecision(False, "invalid", "A valid website URL is required.")
    try:
        host = (urlsplit(url.strip()).hostname or "").casefold().rstrip(".")
    except ValueError:
        host = ""
    prompt = str(user_prompt).casefold()
    normalized_host = host.removeprefix("www.")
    explicitly_named = bool(
        normalized_host
        and re.search(rf"(?<![a-z0-9.-]){re.escape(normalized_host)}(?![a-z0-9.-])", prompt)
    )
    if not explicitly_named:
        for alias, domain in SITE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", prompt) and (
                normalized_host == domain or normalized_host.endswith("." + domain)
            ):
                explicitly_named = True
                break
    if not host or not explicitly_named:
        return ToolDecision(False, "not_requested", "The user did not name this website.")
    return ToolDecision(True, "allowed", "The user explicitly requested this website.")
