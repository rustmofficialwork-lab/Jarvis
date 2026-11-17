"""Small, strictly allowlisted tools for JARVIS AI conversations.

Only deterministic, read-only utilities are exposed to the model. This module
never executes shell commands, Python supplied by a model, or filesystem work.
"""
from __future__ import annotations

import ast
import json
import math
import operator
import subprocess
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Any

from system_monitor import get_system_status, get_top_processes

MAX_EXPRESSION_LENGTH = 120
MAX_ABS_RESULT = 1_000_000_000_000
MAX_POWER = 8
MAX_PROCESS_RESULTS = 10

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression. Use only for calculations.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "maxLength": MAX_EXPRESSION_LENGTH}},
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_local_time",
            "description": "Get the computer's current local date, time, and timezone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Read a live, local-only snapshot of CPU, RAM, disk, battery, network link, and uptime. Read-only; use when the user asks about this PC's health or resources.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": "Read the names and resource usage of up to 10 running processes. Read-only; use only when the user asks which apps or processes are using PC resources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PROCESS_RESULTS}
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a public website in the user's default browser only when the user explicitly asks to visit that URL. Read-only navigation; do not submit forms or enter credentials.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "minLength": 8, "maxLength": 2048}
            }, "required": ["url"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_automation",
            "description": "Control the visible JARVIS browser for the user's directly requested ordinary website task. Actions: navigate to a public HTTPS URL, open or switch tabs, read the page, click a visible element, fill a form field, select an option, press a navigation key, scroll, download a safe file, or upload a selected file. Form submission, file uploads, and sensitive controls require exact one-time voice approval. Safe downloads are stored in Downloads. Purchases, checkout, and payments are disabled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["navigate", "read", "click", "fill", "select", "press", "scroll", "download", "upload", "new_tab", "switch_tab"]},
                    "url": {"type": "string", "maxLength": 2048},
                    "selector": {"type": "string", "maxLength": 240},
                    "value": {"type": "string", "maxLength": 4000}
                },
                "required": ["action"],
                "additionalProperties": false
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send one user-requested email using an already configured Gmail or Microsoft Graph connection. Always show exact recipient, subject, and final body aloud and obtain one-time voice approval before sending. Never send without approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["gmail", "outlook"]},
                    "recipient": {"type": "string", "maxLength": 320},
                    "subject": {"type": "string", "maxLength": 240},
                    "content": {"type": "string", "maxLength": 2500}
                },
                "required": ["provider", "recipient", "subject", "content"],
                "additionalProperties": false
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send one user-requested message using an already configured Telegram or WhatsApp Cloud API connection. Always show exact recipient and final message aloud and obtain one-time voice approval before sending. Never send without approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["telegram", "whatsapp"]},
                    "recipient": {"type": "string", "maxLength": 80},
                    "content": {"type": "string", "maxLength": 2500}
                },
                "required": ["provider", "recipient", "content"],
                "additionalProperties": false
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open one of the built-in safe Windows apps when the user explicitly asks to open it. Never pass arbitrary commands, paths, or arguments.",
            "parameters": {"type": "object", "properties": {
                "app": {"type": "string", "enum": ["notepad", "calculator", "paint", "file_explorer", "task_manager"]}
            }, "required": ["app"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_capabilities",
            "description": "Return the currently implemented JARVIS tool capabilities and important limitations. Use when asked what JARVIS can do or before promising an action.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_provider_integration_status",
            "description": "Report which optional provider adapters are configured without exposing credential values. Read-only status only; this tool never sends messages or changes accounts.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_files",
            "description": "List filenames in Desktop, Documents, or Downloads. Read-only; never lists system or application data.",
            "parameters": {"type": "object", "properties": {
                "folder": {"type": "string", "enum": ["Desktop", "Documents", "Downloads"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30}
            }, "required": ["folder"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_user_files",
            "description": "Search filenames, not file contents, in Desktop, Documents, or Downloads. Read-only.",
            "parameters": {"type": "object", "properties": {
                "folder": {"type": "string", "enum": ["Desktop", "Documents", "Downloads"]},
                "query": {"type": "string", "minLength": 1, "maxLength": 80},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30}
            }, "required": ["folder", "query"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_user_text_file",
            "description": "Read a small plain-text file from Desktop, Documents, or Downloads. Read-only; never use for passwords, keys, tokens, or secrets.",
            "parameters": {"type": "object", "properties": {
                "folder": {"type": "string", "enum": ["Desktop", "Documents", "Downloads"]},
                "filename": {"type": "string", "maxLength": 180}
            }, "required": ["folder", "filename"], "additionalProperties": False}
        }
    },
]


def _safe_number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Only numeric arithmetic is supported.")
    if not math.isfinite(value) or abs(value) > MAX_ABS_RESULT:
        raise ValueError("The result is outside the supported range.")
    return value


def _evaluate_node(node: ast.AST, depth: int = 0) -> int | float:
    if depth > 20:
        raise ValueError("Expression is too complex.")
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, depth + 1)
    if isinstance(node, ast.Constant):
        return _safe_number(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left, depth + 1)
        right = _evaluate_node(node.right, depth + 1)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER:
                raise ValueError("Powers are limited to an exponent of 8.")
            result = left ** right
        else:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        return _safe_number(result)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _safe_number(_UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand, depth + 1)))
    raise ValueError("Use numbers, parentheses, and basic arithmetic operators only.")


def calculate(expression: str) -> str:
    if not isinstance(expression, str):
        raise ValueError("Expression must be text.")
    expression = expression.strip()
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expression must contain 1 to 120 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
        result = _evaluate_node(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("That arithmetic expression could not be evaluated.") from exc
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


_USER_FOLDERS = {"Desktop", "Documents", "Downloads"}
_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
_BLOCKED_NAMES = {"credentials", "secrets", "id_rsa", "id_ed25519", "known_hosts", "config"}
MAX_TEXT_FILE_BYTES = 64 * 1024


def _user_folder(folder: str):
    from pathlib import Path

    if folder not in _USER_FOLDERS:
        raise ValueError("Choose Desktop, Documents, or Downloads.")
    home = Path.home().resolve()
    path = (home / folder).resolve()
    if path.parent != home or not path.is_dir():
        raise ValueError(f"The {folder} folder is not available.")
    return path


def _safe_user_file(folder: str, filename: str):
    if not isinstance(filename, str) or not filename.strip() or len(filename) > 180:
        raise ValueError("Provide a valid filename.")
    name = filename.strip()
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("Only a filename inside the selected folder is allowed.")
    root = _user_folder(folder)
    try:
        path = (root / name).resolve(strict=True)
        path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError("That file does not exist inside the selected folder.") from exc
    if not path.is_file():
        raise ValueError("The selected item is not a regular file.")
    if path.name.casefold() in _BLOCKED_NAMES or path.suffix.casefold() in {".key", ".pem", ".p12", ".pfx", ".db", ".sqlite", ".env"}:
        raise ValueError("For safety, JARVIS cannot read credential, database, or key files.")
    return path


def _list_user_files(folder: str, limit: int = 20, query: str = "") -> str:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 30:
        raise ValueError("Limit must be from 1 to 30.")
    root = _user_folder(folder)
    matches = []
    try:
        for item in root.iterdir():
            if item.name.startswith(".") or item.name.casefold() in _BLOCKED_NAMES or item.is_symlink():
                continue
            if query and query.casefold() not in item.name.casefold():
                continue
            if item.is_file() or item.is_dir():
                matches.append(item.name + ("/" if item.is_dir() else ""))
            if len(matches) >= limit:
                break
    except OSError as exc:
        raise ValueError(f"Could not list that folder: {exc}") from exc
    return "\n".join(matches) if matches else "No matching files or folders found."


def _read_user_text_file(folder: str, filename: str) -> str:
    path = _safe_user_file(folder, filename)
    if path.suffix.casefold() not in _TEXT_EXTENSIONS:
        raise ValueError("Only .txt, .md, .csv, .json, and .log files can be read.")
    if path.stat().st_size > MAX_TEXT_FILE_BYTES:
        raise ValueError("That file is larger than the 64 KB safe reading limit.")
    try:
        return path.read_text(encoding="utf-8")[:MAX_TEXT_FILE_BYTES]
    except UnicodeDecodeError as exc:
        raise ValueError("That file is not valid UTF-8 text.") from exc




_WINDOWS_APP_COMMANDS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file_explorer": ["explorer.exe"],
    "task_manager": ["taskmgr.exe"],
}


def _open_app(app: str) -> str:
    if sys.platform != "win32":
        raise ValueError("Opening Windows apps is supported only on Windows.")
    command = _WINDOWS_APP_COMMANDS.get(app)
    if command is None:
        raise ValueError("That app is not in JARVIS's safe app allowlist.")
    try:
        subprocess.Popen(command, shell=False, close_fds=True)
    except OSError as exc:
        raise ValueError(f"Could not open {app}: {exc}") from exc
    return f"Launch request sent for {app}. The app process was started; check the desktop to confirm it opened."


def _available_capabilities() -> str:
    return (
        "Implemented local tools: calculator; local date/time; PC health snapshot; "
        "top running process usage; list/search filenames in Desktop, Documents, Downloads; "
        "read small UTF-8 txt/md/csv/json/log files in those folders; open Notepad, Calculator, "
        "Paint, File Explorer, and Task Manager on Windows; open a public website in the default browser when explicitly requested. "
        "Online services implemented separately: web search, weather, and news. "
        "Offline AI depends on the local Ollama model being installed and running. "
        "A visible, bounded Playwright browser controller supports public HTTPS navigation, page reading, ordinary clicks, form filling, option selection, scrolling, safe downloads, and approval-gated uploads. Sensitive controls and form submission require exact one-time voice approval. "
        "Email and messaging tools support configured Gmail, Outlook, Telegram, and WhatsApp providers; every send requires exact one-time voice approval. "
        "Shopping research and product comparison can use ordinary browser navigation and search forms; checkout, purchases, and payments are disabled. "
        "Account mutations, unrestricted shell commands, and arbitrary file deletion are not implemented. "
        "Never claim these unsupported actions were completed."
    )



def _open_website(url: str) -> str:
    if not isinstance(url, str) or not 8 <= len(url) <= 2048:
        raise ValueError("Provide a valid public website URL.")
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Only complete HTTP or HTTPS website URLs are supported.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing usernames or passwords are blocked.")
    host = parsed.hostname.rstrip(".").casefold()
    if host in {"localhost", "localhost.localdomain"} or "." not in host:
        raise ValueError("Local, intranet, and single-label hostnames are blocked.")
    try:
        import ipaddress
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private or non-public IP addresses are blocked.")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Non-standard website ports are blocked.")
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    try:
        opened = webbrowser.open(safe_url, new=2, autoraise=True)
    except Exception as exc:
        raise ValueError(f"Could not open the browser: {exc}") from exc
    if not opened:
        raise ValueError("Windows did not confirm that a browser window was opened.")
    return "Browser open request accepted for the public website. JARVIS has not signed in, submitted forms, or changed anything on that site."


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute one allowlisted, read-only tool with exact argument validation."""
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    if name == "calculator":
        if set(arguments) != {"expression"}:
            raise ValueError("Calculator requires only an expression.")
        return calculate(arguments["expression"])
    if name == "get_local_time":
        if arguments:
            raise ValueError("The time tool does not accept arguments.")
        return datetime.now().astimezone().isoformat(timespec="seconds")
    if name == "get_system_status":
        if arguments:
            raise ValueError("The system status tool does not accept arguments.")
        return get_system_status()
    if name == "get_top_processes":
        if set(arguments) - {"limit"}:
            raise ValueError("Top processes accepts only an optional limit.")
        limit = arguments.get("limit", 5)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PROCESS_RESULTS:
            raise ValueError("Process limit must be an integer from 1 to 10.")
        return get_top_processes(limit=limit)
    if name == "browser_automation":
        raise ValueError("Browser automation must be executed through JARVIS's trusted visible-browser controller.")
    if name == "open_website":
        if set(arguments) != {"url"}:
            raise ValueError("Website opening requires only a URL.")
        return _open_website(arguments["url"])
    if name == "open_app":
        if set(arguments) != {"app"} or not isinstance(arguments["app"], str):
            raise ValueError("Opening an app requires only its allowlisted app name.")
        return _open_app(arguments["app"])
    if name == "get_available_capabilities":
        if arguments:
            raise ValueError("The capabilities tool does not accept arguments.")
        return _available_capabilities()
    if name == "get_provider_integration_status":
        if arguments:
            raise ValueError("Provider integration status does not accept arguments.")
        from provider_integrations import integration_status
        return json.dumps(integration_status(), sort_keys=True)
    if name == "list_user_files":
        if set(arguments) - {"folder", "limit"} or "folder" not in arguments:
            raise ValueError("File listing requires folder and optional limit.")
        return _list_user_files(arguments["folder"], arguments.get("limit", 20))
    if name == "search_user_files":
        if set(arguments) - {"folder", "query", "limit"} or not {"folder", "query"} <= set(arguments):
            raise ValueError("File search requires folder and query, plus optional limit.")
        query = arguments["query"]
        if not isinstance(query, str) or not query.strip() or len(query) > 80:
            raise ValueError("Search query must contain 1 to 80 characters.")
        return _list_user_files(arguments["folder"], arguments.get("limit", 20), query.strip())
    if name == "read_user_text_file":
        if set(arguments) != {"folder", "filename"}:
            raise ValueError("Text file reading requires only folder and filename.")
        return _read_user_text_file(arguments["folder"], arguments["filename"])
    raise ValueError("That JARVIS tool is not available.")
