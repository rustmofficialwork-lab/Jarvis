"""Optional, bounded integrations for JARVIS.

Provider credentials are read only from the local process environment. This module
never stores tokens, never follows HTTP redirects, and requires an exact one-time
approval callback immediately before sending email or a message.

Browser support is read-only and requires Playwright plus an exact hostname
allowlist. Payment, checkout, purchases, and account/security mutations are
intentionally not implemented.
"""
from __future__ import annotations

import base64
import json
import os
import ipaddress
import re
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Callable, Any

HTTP_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 10_000
MAX_BROWSER_TEXT_CHARS = 20_000


class IntegrationUnavailable(RuntimeError):
    """A provider is not configured or its optional dependency is missing."""


class IntegrationRejected(RuntimeError):
    """A provider rejected the request or its response was unsafe."""


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise IntegrationUnavailable(
            f"{name} is not configured. Add it locally in JARVIS's trusted settings; do not paste secrets into chat."
        )
    if len(value) > 8192 or any(ord(ch) < 32 for ch in value):
        raise IntegrationUnavailable(f"{name} has an invalid format.")
    return value


def _request_json(url: str, *, method: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise IntegrationRejected("Provider response exceeded the safe size limit.")
            result = json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read(512).decode("utf-8", errors="replace")
        raise IntegrationRejected(f"Provider rejected the request (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise IntegrationRejected(f"Provider connection failed: {exc.reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationRejected("Provider returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise IntegrationRejected("Provider returned an unexpected response.")
    return result


def _validate_text(value: str, label: str, *, maximum: int = MAX_MESSAGE_CHARS) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"{label} must contain 1 to {maximum} characters.")
    return value


def _validate_recipient(value: str) -> str:
    recipient = _validate_text(value, "Recipient", maximum=320)
    if any(ch in recipient for ch in "\r\n") or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", recipient):
        raise ValueError("A single valid email address is required.")
    return recipient


def _consume(consume_approval: Callable[[dict[str, Any]], Any], details: dict[str, Any]) -> None:
    if not callable(consume_approval):
        raise PermissionError("A trusted one-time approval callback is required.")
    decision = consume_approval(details)
    if not getattr(decision, "approved", False):
        raise PermissionError("Exact one-time approval was not granted; nothing was sent.")


def send_gmail_email(
    recipient: str, subject: str, content: str, *,
    consume_approval: Callable[[dict[str, Any]], Any],
) -> str:
    """Send one Gmail message using a pre-authorized OAuth access token."""
    recipient = _validate_recipient(recipient)
    subject = _validate_text(subject, "Subject", maximum=240)
    content = _validate_text(content, "Message")
    details = {"recipient": recipient, "subject": subject, "content": content}
    _consume(consume_approval, details)
    token = _required_env("JARVIS_GMAIL_ACCESS_TOKEN")
    sender = _required_env("JARVIS_GMAIL_USER")
    if sender.casefold() != sender.strip().casefold() or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", sender):
        raise IntegrationUnavailable("JARVIS_GMAIL_USER must be the authorized Gmail address.")
    message = EmailMessage()
    message["To"] = recipient
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(content)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    _request_json(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        method="POST", token=token, payload={"raw": raw},
    )
    return f"Gmail accepted the message for {recipient}."


def send_outlook_email(
    recipient: str, subject: str, content: str, *,
    consume_approval: Callable[[dict[str, Any]], Any],
) -> str:
    """Send one Microsoft 365 message using a pre-authorized Graph token."""
    recipient = _validate_recipient(recipient)
    subject = _validate_text(subject, "Subject", maximum=240)
    content = _validate_text(content, "Message")
    _consume(consume_approval, {"recipient": recipient, "subject": subject, "content": content})
    token = _required_env("JARVIS_GRAPH_ACCESS_TOKEN")
    _request_json(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        method="POST", token=token,
        payload={
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": content},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
            },
            "saveToSentItems": True,
        },
    )
    return f"Microsoft Graph accepted the message for {recipient}."


def send_telegram_message(
    recipient_chat_id: str, content: str, *,
    consume_approval: Callable[[dict[str, Any]], Any],
) -> str:
    """Send one Telegram message to an explicitly selected chat ID."""
    chat_id = _validate_text(recipient_chat_id, "Telegram chat ID", maximum=80)
    if not re.fullmatch(r"-?[0-9]{1,25}", chat_id):
        raise ValueError("Telegram chat ID must be a numeric chat identifier.")
    content = _validate_text(content, "Message")
    _consume(consume_approval, {"recipient": chat_id, "content": content})
    token = _required_env("JARVIS_TELEGRAM_BOT_TOKEN")
    result = _request_json(
        f"https://api.telegram.org/bot{token}/sendMessage",
        method="POST", token=token, payload={"chat_id": chat_id, "text": content},
    )
    if result.get("ok") is not True:
        raise IntegrationRejected("Telegram did not confirm message delivery.")
    return f"Telegram accepted the message for chat {chat_id}."


def send_whatsapp_message(
    phone_number: str, content: str, *,
    consume_approval: Callable[[dict[str, Any]], Any],
) -> str:
    """Send a text message through the official WhatsApp Cloud API."""
    phone = _validate_text(phone_number, "WhatsApp phone number", maximum=32)
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        raise ValueError("Use an international phone number such as +14155550123.")
    content = _validate_text(content, "Message")
    _consume(consume_approval, {"recipient": phone, "content": content})
    token = _required_env("JARVIS_WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _required_env("JARVIS_WHATSAPP_PHONE_NUMBER_ID")
    version = os.environ.get("JARVIS_WHATSAPP_API_VERSION", "v22.0").strip()
    if not re.fullmatch(r"v[0-9]{1,2}\.[0-9]{1,2}", version):
        raise IntegrationUnavailable("JARVIS_WHATSAPP_API_VERSION must use the official vNN.N format.")
    result = _request_json(
        f"https://graph.facebook.com/{version}/{urllib.parse.quote(phone_number_id, safe='')}/messages",
        method="POST", token=token,
        payload={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": content},
        },
    )
    if not isinstance(result.get("messages"), list) or not result["messages"]:
        raise IntegrationRejected("WhatsApp Cloud API did not confirm message acceptance.")
    return f"WhatsApp Cloud API accepted the message for {phone}."


def run_approved_action(
    app: Any, action_type: str, details: dict[str, Any], summary: str,
    executor: Callable[[Callable[[dict[str, Any]], Any]], str],
) -> str:
    """Bridge a provider executor to JARVIS's native voice approval and one-use ledger."""
    request_permission = getattr(app, "request_sensitive_action_approval", None)
    brain = getattr(app, "brain_engine", None)
    consume = getattr(brain, "consume_sensitive_approval", None)
    if not callable(request_permission) or not callable(consume):
        raise PermissionError("JARVIS trusted voice approval is unavailable; action was not run.")
    if not request_permission(action_type, details, summary):
        raise PermissionError("User denied or could not complete voice approval; action was not run.")

    def consume_exact(approved_details: dict[str, Any]):
        if approved_details != details:
            raise PermissionError("Approved action details changed; action was not run.")
        return consume(action_type, approved_details)

    return executor(consume_exact)


def read_browser_page(
    url: str, *, allowed_domains: list[str], consume_approval: Callable[[dict[str, Any]], Any],
) -> str:
    """Read visible page text on an explicitly allowlisted host; never click or submit."""
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Provide one valid website URL.")
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Browser automation requires a public HTTPS URL without embedded credentials.")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if (address is not None and not address.is_global) or (address is None and (
        "." not in host or host.endswith((".local", ".localhost", ".internal", ".test"))
    )):
        raise ValueError("Local, private, and non-public browser hosts are blocked.")
    if not isinstance(allowed_domains, list) or host not in {str(x).casefold() for x in allowed_domains}:
        raise PermissionError("The exact website hostname is not allowlisted.")
    details = {"domain": host, "action": "read_page"}
    _consume(consume_approval, details)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise IntegrationUnavailable("Install the optional Playwright browser runtime to use read-only browser automation.") from exc
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_navigation_timeout(10_000)

            def restrict_requests(route):
                requested = urllib.parse.urlsplit(route.request.url)
                request_host = (requested.hostname or "").casefold().rstrip(".")
                if requested.scheme == "https" and request_host == host:
                    route.continue_()
                else:
                    route.abort()

            page.route("**/*", restrict_requests)
            page.goto(url, wait_until="domcontentloaded")
            final_host = (urllib.parse.urlsplit(page.url).hostname or "").casefold().rstrip(".")
            if final_host != host:
                raise PermissionError("The page redirected to a different hostname; navigation was stopped.")
            text = page.locator("body").inner_text(timeout=5_000)
            return text[:MAX_BROWSER_TEXT_CHARS]
        finally:
            browser.close()


def integration_status() -> dict[str, str]:
    """Report configuration presence only; never expose credential values."""
    import importlib.util
    playwright_ready = importlib.util.find_spec("playwright") is not None
    return {
        "gmail": "configured" if os.environ.get("JARVIS_GMAIL_ACCESS_TOKEN") and os.environ.get("JARVIS_GMAIL_USER") else "needs_local_oauth_setup",
        "microsoft_graph": "configured" if os.environ.get("JARVIS_GRAPH_ACCESS_TOKEN") else "needs_local_oauth_setup",
        "telegram": "configured" if os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN") else "needs_local_bot_setup",
        "whatsapp": "configured" if all(os.environ.get(k) for k in ("JARVIS_WHATSAPP_ACCESS_TOKEN", "JARVIS_WHATSAPP_PHONE_NUMBER_ID")) else "needs_official_cloud_api_setup",
        "playwright": "installed" if playwright_ready else "optional_dependency_missing",
        "payments": "disabled_test_mode_only",
        "purchases": "disabled_test_mode_only",
        "account_mutations": "not_implemented_read_only_only",
    }
