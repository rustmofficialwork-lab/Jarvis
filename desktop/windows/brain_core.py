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
    "get_provider_integration_status",
})
# Personal file access is read-only but still privacy-sensitive: it must be
# grounded in a direct file-related request, not merely a model suggestion.
USER_DIRECTED_FILE_TOOLS = frozenset({
    "list_user_files", "search_user_files", "read_user_text_file",
})
USER_DIRECTED_TOOLS = frozenset({"open_app", "open_website"})
BROWSER_ACTION_TOOLS = frozenset({"browser_automation"})
# Exact domain aliases prevent deceptive hosts such as youtube.com.attacker.invalid.
SITE_ALIASES = {"youtube": "youtube.com", "google": "google.com", "github": "github.com", "gmail": "mail.google.com", "wikipedia": "wikipedia.org", "reddit": "reddit.com", "stackoverflow": "stackoverflow.com", "amazon": "amazon.com", "flipkart": "flipkart.com", "ebay": "ebay.com", "myntra": "myntra.com"}
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


def _explicit_file_request(tool: str, arguments: dict[str, Any], prompt: str) -> bool:
    """Require direct intent and a user-named folder/file before inspecting personal data."""
    text = str(prompt or "").strip().casefold()
    folder = arguments.get("folder")
    if not isinstance(folder, str) or not re.search(rf"\b{re.escape(folder.casefold())}\b", text):
        return False
    if tool == "read_user_text_file":
        filename = arguments.get("filename")
        if not isinstance(filename, str) or not filename.strip() or filename.casefold() not in text:
            return False
    if re.search(
        r"\b(don't|do not|never|avoid|mat|nahi|nahin)\b.{0,60}\b"
        r"(read|open|list|search|find|locate|inspect|check|summarize|"
        r"analyze|show|display)\b",
        text,
    ):
        return False

    object_pattern = r"(?:my\s+)?(?:files?|folders?|documents?|downloads?|desktop)"
    if tool == "list_user_files":
        action_pattern = r"(?:list|show|display)"
    elif tool == "search_user_files":
        action_pattern = r"(?:search|find|locate|look\s+for)"
    else:
        action_pattern = r"(?:read|open|inspect|check|summarize|analyze|what(?:'s|\s+is)\s+in)"
    return bool(
        re.search(rf"\b{action_pattern}\b.{{0,50}}\b{object_pattern}\b", text)
        or re.search(rf"\b{object_pattern}\b.{{0,50}}\b{action_pattern}\b", text)
    )


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
    if tool in BROWSER_ACTION_TOOLS:
        action = arguments.get("action")
        if action not in {"navigate", "read", "click", "fill", "select", "press", "scroll"}:
            return ToolDecision(False, "invalid", "Unsupported browser action.")
        prompt = str(user_prompt or "").casefold()
        direct_verbs = {
            "navigate": ("open", "visit", "go to", "navigate", "kholo", "khol do"),
            "read": ("read", "show", "summarize", "check", "padho", "dikhao"),
            "click": ("click", "press", "select", "dabao", "click karo"),
            "fill": ("fill", "type", "enter", "search", "likho", "bharo"),
            "select": ("select", "choose", "pick", "chuno"),
            "press": ("press", "tab", "escape"),
            "scroll": ("scroll", "neeche", "upar"),
        }[action]
        if not any(re.search(rf"\b{re.escape(verb)}\b", prompt) for verb in direct_verbs):
            return ToolDecision(False, "not_requested", "The user did not directly request this browser action.")
        if action == "navigate":
            url = arguments.get("url")
            try:
                host = (urlsplit(url.strip()).hostname or "").casefold().removeprefix("www.") if isinstance(url, str) else ""
            except ValueError:
                host = ""
            named = bool(host and re.search(rf"(?<![a-z0-9-]){re.escape(host)}(?![a-z0-9-])", prompt))
            if not named:
                for alias, domain in SITE_ALIASES.items():
                    if re.search(rf"\b{re.escape(alias)}\b", prompt) and host in {domain, "www." + domain}:
                        named = True
                        break
            if not named:
                return ToolDecision(False, "not_requested", "The user must name the website being opened.")
        return ToolDecision(True, "allowed", "The user directly requested this bounded browser action.")
    if tool in USER_DIRECTED_FILE_TOOLS:
        if not _explicit_file_request(tool, arguments, user_prompt):
            return ToolDecision(
                False, "not_requested",
                "The user did not directly request access to personal files.",
            )
        return ToolDecision(
            True, "allowed", "The user explicitly requested this personal-file operation."
        )
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
        and re.search(rf"(?<![a-z0-9-]){re.escape(normalized_host)}(?![a-z0-9-])", prompt)
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
