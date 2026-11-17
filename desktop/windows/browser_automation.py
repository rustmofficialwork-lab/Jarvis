"""Visible, bounded Playwright automation for ordinary website workflows.

The browser uses a dedicated JARVIS profile, never the user's personal browser
profile. Navigation and ordinary page interaction do not request voice approval.
Irreversible or sensitive controls are detected and blocked for a separate
trusted approval flow; checkout, purchases, and payments are never executable.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import threading
import urllib.parse
from pathlib import Path
from typing import Any

MAX_STEPS_PER_SESSION = 40
MAX_TEXT_CHARS = 16_000
MAX_SELECTOR_CHARS = 240
FINANCIAL_LABELS = re.compile(r"\b(pay|payment|purchase|buy now|place order|submit order|checkout|cart|add to cart)\b", re.IGNORECASE)
SENSITIVE_LABELS = re.compile(
    r"\b(pay|payment|purchase|buy now|place order|submit order|checkout|"
    r"send|transfer|delete|remove account|change password|confirm booking)\b",
    re.IGNORECASE,
)
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


class BrowserAutomationError(RuntimeError):
    """A browser action was refused or could not be completed safely."""


class BrowserAutomation:
    """One visible Chromium session, isolated to a dedicated JARVIS profile."""

    def __init__(self, profile_dir: str | Path):
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self._lock = threading.RLock()
        self._playwright = None
        self._context = None
        self._page = None
        self._host: str | None = None
        self._steps = 0

    @staticmethod
    def _validate_url(url: str) -> tuple[str, str]:
        if not isinstance(url, str) or not 8 <= len(url) <= 2048:
            raise ValueError("Provide one valid website URL.")
        parsed = urllib.parse.urlsplit(url.strip())
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            raise ValueError("Browser automation requires a public HTTPS URL without embedded credentials.")
        if parsed.port not in (None, 443) or host in _BLOCKED_HOSTS or "." not in host:
            raise ValueError("Local, private, and non-standard-port websites are blocked.")
        try:
            address = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            address = None
        if address is not None:
            if not address.is_global:
                raise ValueError("Private or non-public IP addresses are blocked.")
        else:
            try:
                resolved = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise BrowserAutomationError("The website hostname could not be resolved.") from exc
            for item in resolved:
                ip = ipaddress.ip_address(item[4][0])
                if not ip.is_global:
                    raise ValueError("The website resolves to a private or non-public address.")
        return host, urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))

    def _ensure_browser(self):
        if self._context is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAutomationError(
                "Playwright is not installed. Install desktop/windows/requirements.txt and run 'py -m playwright install chromium'."
            ) from exc
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                accept_downloads=False,
                args=["--disable-sync", "--no-first-run"],
            )
            self._context.set_default_timeout(8_000)
            self._context.set_default_navigation_timeout(15_000)
            self._context.on("page", lambda page: page.close() if page != self._page else None)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        except Exception:
            self.close()
            raise

    def close(self):
        with self._lock:
            try:
                if self._context is not None:
                    self._context.close()
            finally:
                self._context = None
                self._page = None
                self._host = None
                if self._playwright is not None:
                    self._playwright.stop()
                self._playwright = None

    def _check_step(self):
        if self._steps >= MAX_STEPS_PER_SESSION:
            raise BrowserAutomationError("Browser task step limit reached; start a new task.")
        self._steps += 1

    def _require_page(self):
        if self._page is None or self._page.is_closed():
            raise BrowserAutomationError("No active JARVIS browser page. Navigate to a website first.")
        current_host = (urllib.parse.urlsplit(self._page.url).hostname or "").casefold().rstrip(".")
        if current_host != self._host:
            raise BrowserAutomationError("The active page left its approved website; navigate again.")
        return self._page

    def _safe_target(self, page):
        def route_request(route):
            parsed = urllib.parse.urlsplit(route.request.url)
            request_host = (parsed.hostname or "").casefold().rstrip(".")
            if parsed.scheme == "https" and request_host == self._host:
                route.continue_()
            else:
                route.abort()
        page.route("**/*", route_request)

    def navigate(self, url: str) -> str:
        host, safe_url = self._validate_url(url)
        with self._lock:
            self._check_step()
            self._ensure_browser()
            if self._host is not None and host != self._host:
                self._host = None
            self._host = host
            self._safe_target(self._page)
            self._page.goto(safe_url, wait_until="domcontentloaded")
            final_host = (urllib.parse.urlsplit(self._page.url).hostname or "").casefold().rstrip(".")
            if final_host != host:
                self._page.goto("about:blank")
                self._host = None
                raise BrowserAutomationError("Cross-domain redirect blocked. Open the destination explicitly.")
            return self._describe_page()

    def _describe_page(self) -> str:
        page = self._require_page()
        title = page.title()[:240]
        url = page.url[:2048]
        text = page.locator("body").inner_text(timeout=5_000)[:MAX_TEXT_CHARS]
        return f"Page: {title}\nURL: {url}\n\n{text}"

    def act(self, action: str, *, selector: str = "", value: str = "", url: str = "", approval_callback=None) -> str:
        if action == "navigate":
            return self.navigate(url)
        if action not in {"read", "click", "fill", "select", "press", "scroll"}:
            raise ValueError("Unsupported browser action.")
        if not isinstance(selector, str) or len(selector) > MAX_SELECTOR_CHARS:
            raise ValueError("Selector must be 240 characters or fewer.")
        if action in {"fill", "select", "press"} and (not isinstance(value, str) or len(value) > 4000):
            raise ValueError("Input value must be 4000 characters or fewer.")
        with self._lock:
            self._check_step()
            page = self._require_page()
            if action == "read":
                return self._describe_page()
            if action == "scroll":
                page.mouse.wheel(0, 650)
                return "Scrolled the current page."
            if not selector.strip():
                raise ValueError("A visible text, label, role, or CSS selector is required.")
            locator = page.locator(selector).first
            if locator.count() != 1 or not locator.is_visible():
                raise BrowserAutomationError("The selector did not identify one visible element.")
            if action == "click":
                label = " ".join([
                    str(locator.inner_text(timeout=1500) or ""),
                    str(locator.get_attribute("aria-label") or ""),
                    str(locator.get_attribute("title") or ""),
                    str(locator.get_attribute("value") or ""),
                ]).strip()[:500]
                if FINANCIAL_LABELS.search(label):
                    raise PermissionError("Purchases, checkout, and payment controls are disabled.")
                if SENSITIVE_LABELS.search(label):
                    details = {"domain": self._host, "action": "click_sensitive_control",
                               "label": label[:240], "selector": selector[:240]}
                    if not callable(approval_callback) or not approval_callback(
                        details, f"Click sensitive website control: {label[:160]}"
                    ):
                        raise PermissionError("Sensitive website action was not approved; nothing was clicked.")
                locator.click()
                return f"Clicked the selected page element: {label[:160] or selector}."
            if action == "fill":
                locator.fill(value)
                return "Filled the selected form field. The form was not submitted."
            if action == "select":
                locator.select_option(label=value)
                return "Selected the requested option. The form was not submitted."
            if action == "press":
                if value.casefold() in {"enter", "return"}:
                    details = {"domain": self._host, "action": "submit_form",
                               "selector": selector[:240], "key": "Enter"}
                    if not callable(approval_callback) or not approval_callback(
                        details, "Submit the current website form"
                    ):
                        raise PermissionError("Form submission was not approved; the form was not submitted.")
                if value.casefold() not in {"tab", "escape", "arrowdown", "arrowup", "home", "end"}:
                    raise ValueError("Only navigation keys are supported.")
                locator.press(value)
                return f"Pressed {value} on the selected element."
        raise BrowserAutomationError("The browser action did not complete.")

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._context is not None,
                "domain": self._host,
                "steps_used": self._steps,
                "step_limit": MAX_STEPS_PER_SESSION,
                "profile": "dedicated_jarvis_profile",
                "checkout_and_payments": "disabled",
            }
