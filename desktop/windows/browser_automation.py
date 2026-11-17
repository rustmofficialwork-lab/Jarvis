"""Visible, bounded Playwright automation for ordinary website workflows.

The browser uses a dedicated JARVIS profile, never the user's personal browser
profile. Navigation and ordinary page interaction do not request voice approval.
Irreversible or sensitive controls are detected and blocked for a separate
trusted approval flow; checkout, purchases, and payments are never executable.
"""
from __future__ import annotations

import ipaddress
import os
import queue
import re
import socket
import threading
from concurrent.futures import Future
import urllib.parse
from pathlib import Path
from typing import Any

MAX_STEPS_PER_SESSION = 40
MAX_TEXT_CHARS = 5_000
MAX_SELECTOR_CHARS = 240
FINANCIAL_LABELS = re.compile(r"\b(pay|payment|purchase|buy now|place order|submit order|checkout|cart|add to cart)\b", re.IGNORECASE)\nFINANCIAL_CONTEXT_PATTERN = re.compile(r"\b(checkout|payment|billing|cart|purchase|order)\b", re.IGNORECASE)
PERSONAL_FIELD_PATTERN = re.compile(r"\b(name|email|phone|mobile|address|postal|zip|date of birth|dob|passport|national id)\b", re.IGNORECASE)
SENSITIVE_LABELS = re.compile(
    r"\b(pay|payment|purchase|buy now|place order|submit order|checkout|"
    r"send|transfer|delete|remove account|change password|change email|change username|update account|save changes|edit profile|security settings|export|confirm booking|submit|confirm|log in|login|sign in|logout|post|publish|share)\b",
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
        self._page_hosts: dict[int, str | None] = {}
        self._steps = 0
        self._commands: queue.Queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._worker_loop, name="JARVIS-Browser", daemon=True
        )
        self._worker.start()

    def _worker_loop(self):
        while True:
            item = self._commands.get()
            if item is None:
                return
            future, method, args, kwargs = item
            try:
                if method == "act":
                    result = self._act_local(*args, **kwargs)
                elif method == "navigate":
                    result = self._navigate_local(*args, **kwargs)
                elif method == "status":
                    result = self._status_local()
                elif method == "close":
                    result = self._close_local()
                else:
                    raise BrowserAutomationError("Unknown browser worker command.")
                future.set_result(result)
                if method == "close":
                    return
            except BaseException as exc:
                future.set_exception(exc)

    def _call_worker(self, method: str, *args, **kwargs):
        if not self._worker.is_alive():
            raise BrowserAutomationError("The JARVIS browser session has been closed.")
        future = Future()
        self._commands.put((future, method, args, kwargs))
        return future.result(timeout=120)

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
            launch_options = {
                "user_data_dir": str(self.profile_dir),
                "headless": False,
                "accept_downloads": True,
                "args": ["--disable-sync", "--no-first-run"],
            }
            if os.name == "nt":
                launch_options["channel"] = "msedge"
            try:
                self._context = self._playwright.chromium.launch_persistent_context(**launch_options)
            except Exception:
                if os.name != "nt":
                    raise
                # Fall back to the Playwright-managed Chromium runtime if Edge is unavailable.
                launch_options.pop("channel", None)
                self._context = self._playwright.chromium.launch_persistent_context(**launch_options)
            self._context.set_default_timeout(8_000)
            self._context.set_default_navigation_timeout(15_000)
            self._context.on("page", self._attach_page)
            pages = self._context.pages
            if pages:
                self._page = pages[0]
                self._page_hosts[id(self._page)] = self._host
                self._safe_target(self._page)
            else:
                self._page = self._context.new_page()
        except Exception:
            self._close_local()
            raise

    def _attach_page(self, page):
        """Keep newly opened tabs inside their own public-host navigation boundary."""
        self._page = page
        self._page_hosts[id(page)] = self._host
        try:
            self._safe_target(page)
        except Exception:
            page.close()

    def _close_local(self):
        with self._lock:
            try:
                if self._context is not None:
                    self._context.close()
            finally:
                self._context = None
                self._page = None
                self._host = None
                self._page_hosts.clear()
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
        if self._page.url == "about:blank":
            return self._page
        current_host = (urllib.parse.urlsplit(self._page.url).hostname or "").casefold().rstrip(".")
        expected_host = self._page_hosts.get(id(self._page))
        if not expected_host or current_host != expected_host:
            raise BrowserAutomationError("The active page left its approved website; navigate again.")
        self._host = expected_host
        return self._page

    def _safe_target(self, page):
        page_id = id(page)

        def route_request(route):
            try:
                request_host, _safe_url = self._validate_url(route.request.url)
                expected_host = self._page_hosts.get(page_id)
                if route.request.is_navigation_request and request_host != expected_host:
                    route.abort()
                    return
                route.continue_()
            except (TypeError, ValueError, BrowserAutomationError):
                route.abort()
        page.route("**/*", route_request)

    def navigate(self, url: str) -> str:
        return self._call_worker("navigate", url)

    def _navigate_local(self, url: str) -> str:
        host, safe_url = self._validate_url(url)
        with self._lock:
            self._check_step()
            self._ensure_browser()
            self._host = host
            self._page_hosts[id(self._page)] = host
            self._safe_target(self._page)
            self._page.goto(safe_url, wait_until="domcontentloaded")
            final_host = (urllib.parse.urlsplit(self._page.url).hostname or "").casefold().rstrip(".")
            if final_host != host:
                self._page.goto("about:blank")
                self._host = None
                raise BrowserAutomationError("Cross-domain redirect blocked. Open the destination explicitly.")
            return self._describe_page()

    @staticmethod
    def _is_financial_context(page, selector: str = "") -> bool:
        path = urllib.parse.urlsplit(page.url).path
        title = page.title()
        return bool(
            FINANCIAL_CONTEXT_PATTERN.search(path)
            or FINANCIAL_CONTEXT_PATTERN.search(title)
            or FINANCIAL_CONTEXT_PATTERN.search(selector)
        )

    def _describe_page(self) -> str:
        page = self._require_page()
        title = page.title()[:240]
        url = page.url[:2048]
        text = page.locator("body").inner_text(timeout=5_000)[:MAX_TEXT_CHARS]
        controls = page.locator("button, a[href], input, select, textarea, [role='button']")
        control_lines = []
        for index in range(min(controls.count(), 60)):
            try:
                metadata = controls.nth(index).evaluate(
                    """el => {
                        const cssEscape = window.CSS && CSS.escape
                            ? CSS.escape
                            : value => String(value).replace(/[^a-zA-Z0-9_-]/g, ch => '\\\\' + ch);
                        const parts = [];
                        for (let node = el; node && node.nodeType === 1 && node !== document.body; node = node.parentElement) {
                            let part = node.tagName.toLowerCase();
                            if (node.id) {
                                part += '#' + cssEscape(node.id);
                                parts.unshift(part);
                                break;
                            }
                            const parent = node.parentElement;
                            if (parent) {
                                const siblings = Array.from(parent.children).filter(item => item.tagName === node.tagName);
                                if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
                            }
                            parts.unshift(part);
                        }
                        return {
                            tag: el.tagName.toLowerCase(),
                            type: el.getAttribute('type') || '',
                            name: el.getAttribute('name') || '',
                            label: (el.labels && el.labels[0] ? el.labels[0].innerText : '') || el.getAttribute('aria-label') || '',
                            placeholder: el.getAttribute('placeholder') || '',
                            text: (el.innerText || el.textContent || '').trim().slice(0, 100),
                            selector: parts.join(' > ').slice(0, 240)
                        };
                    }"""
                )
                if metadata.get("selector"):
                    summary = " ".join(
                        f"{key}={str(metadata.get(key, '')).replace(chr(10), ' ')[:120]}"
                        for key in ("tag", "type", "label", "placeholder", "text", "selector")
                        if metadata.get(key)
                    )
                    control_lines.append(f"- {summary}")
            except Exception:
                continue
        controls_text = "\n".join(control_lines) or "- No interactive controls detected."
        return (
            f"Page: {title}\nURL: {url}\n\nVisible page text:\n{text}"
            f"\n\nInteractive controls (selectors are for this page only):\n{controls_text}"
        )

    def act(self, action: str, *, selector: str = "", value: str = "", url: str = "", approval_callback=None) -> str:
        return self._call_worker(
            "act", action, selector=selector, value=value, url=url,
            approval_callback=approval_callback,
        )

    def _act_local(self, action: str, *, selector: str = "", value: str = "", url: str = "", approval_callback=None) -> str:
        if action == "navigate":
            return self._navigate_local(url)
        if action not in {"read", "click", "fill", "select", "press", "scroll", "download", "upload", "new_tab", "switch_tab"}:
            raise ValueError("Unsupported browser action.")
        if not isinstance(selector, str) or len(selector) > MAX_SELECTOR_CHARS:
            raise ValueError("Selector must be 240 characters or fewer.")
        if action in {"fill", "select", "press", "upload", "switch_tab"} and (
            not isinstance(value, str) or len(value) > 4000
        ):
            raise ValueError("Input value must be text containing 4000 characters or fewer.")
        with self._lock:
            self._check_step()
            if action in {"new_tab", "switch_tab"}:
                if self._context is None:
                    raise BrowserAutomationError("Open a website before managing browser tabs.")
                if action == "new_tab":
                    page = self._context.new_page()
                    self._page = page
                    return "Opened a new JARVIS browser tab."
                if not value.isdigit():
                    raise ValueError("Provide a zero-based tab number.")
                pages = self._context.pages
                index = int(value)
                if index < 0 or index >= len(pages) or index >= 10:
                    raise ValueError("That browser tab does not exist.")
                self._page = pages[index]
                self._host = self._page_hosts.get(id(self._page))
                if self._page.url == "about:blank":
                    return "Switched to a blank browser tab. Navigate to a public HTTPS website to continue."
                return self._describe_page()
            page = self._require_page()
            if action == "read":
                return self._describe_page()
            if action == "download":
                if self._is_financial_context(page, selector):
                    raise PermissionError("Checkout, cart, and payment workflows are disabled.")
                if not selector.strip():
                    raise ValueError("Select the download link or button.")
                download_matches = page.locator(selector)
                if download_matches.count() != 1 or not download_matches.first.is_visible():
                    raise BrowserAutomationError("The download selector must identify exactly one visible element.")
                download_label = str(download_matches.first.inner_text(timeout=1500) or "")
                if FINANCIAL_LABELS.search(download_label):
                    raise PermissionError("Checkout and payment controls are disabled.")
                if SENSITIVE_LABELS.search(download_label):
                    details = {"domain": self._host, "action": "click_sensitive_control",
                               "label": download_label[:240], "selector": selector[:240]}
                    if not callable(approval_callback) or not approval_callback(
                        details, f"Download sensitive website data from {self._host}"
                    ):
                        raise PermissionError("Sensitive download was not approved.")
                downloads = Path.home() / "Downloads"
                downloads.mkdir(parents=True, exist_ok=True)
                with page.expect_download(timeout=20_000) as pending:
                    page.locator(selector).first.click()
                download = pending.value
                filename = Path(download.suggested_filename).name
                suffix = Path(filename).suffix.casefold()
                if suffix in {".exe", ".msi", ".bat", ".cmd", ".ps1", ".scr", ".com",
                              ".dll", ".sys", ".js", ".vbs", ".jar", ".reg", ".lnk"}:
                    download.cancel()
                    raise PermissionError("Executable or script downloads are blocked.")
                destination = (downloads / filename).resolve()
                if destination.parent != downloads.resolve():
                    raise BrowserAutomationError("Unsafe download filename was blocked.")
                temporary_path = download.path()
                if temporary_path and Path(temporary_path).stat().st_size > 50 * 1024 * 1024:
                    download.cancel()
                    raise BrowserAutomationError("Download exceeded the 50 MB safety limit.")
                if destination.exists():
                    stem, extension = destination.stem, destination.suffix
                    index = 1
                    while destination.exists():
                        destination = downloads / f"{stem} ({index}){extension}"
                        index += 1
                download.save_as(str(destination))
                return f"Downloaded {filename} to the Windows Downloads folder."
            if action == "upload":
                if self._is_financial_context(page, selector):
                    raise PermissionError("File uploads inside checkout and payment workflows are disabled.")
                file_path = Path(value).expanduser().resolve()
                allowed_roots = [
                    (Path.home() / "Desktop").resolve(),
                    (Path.home() / "Documents").resolve(),
                    (Path.home() / "Downloads").resolve(),
                ]
                if not file_path.is_file() or not any(
                    file_path == root or root in file_path.parents for root in allowed_roots
                ):
                    raise ValueError("Choose one existing file from Desktop, Documents, or Downloads.")
                if file_path.stat().st_size > 25 * 1024 * 1024:
                    raise ValueError("Uploads are limited to 25 MB.")
                details = {"domain": self._host, "action": "upload_file",
                           "file": str(file_path), "selector": selector[:240]}
                if not callable(approval_callback) or not approval_callback(
                    details, f"Upload the selected file {file_path.name} to {self._host}"
                ):
                    raise PermissionError("File upload was not approved; no file was uploaded.")
                if not selector.strip():
                    raise ValueError("Select the file input element.")
                matches = page.locator(selector)
                if matches.count() != 1:
                    raise BrowserAutomationError("The file input selector must identify exactly one element.")
                matches.first.set_input_files(str(file_path))
                return f"Selected {file_path.name} for upload to {self._host}."
            if action == "scroll":
                page.mouse.wheel(0, 650)
                return "Scrolled the current page."
            if not selector.strip():
                raise ValueError("A visible text, label, role, or CSS selector is required.")
            matches = page.locator(selector)
            if matches.count() != 1 or not matches.first.is_visible():
                raise BrowserAutomationError("The selector must identify exactly one visible element.")
            locator = matches.first
            if action == "click":
                if self._is_financial_context(page, selector):
                    raise PermissionError("Checkout, cart, and payment workflows are disabled.")
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
                if self._is_financial_context(page, selector):
                    raise PermissionError("Checkout and payment form changes are disabled.")
                field_type = (locator.get_attribute("type") or "").casefold()
                field_name = " ".join([
                    str(locator.get_attribute("name") or ""),
                    str(locator.get_attribute("autocomplete") or ""),
                    str(locator.get_attribute("aria-label") or ""),
                    str(locator.get_attribute("placeholder") or ""),
                ]).casefold()
                field_name = re.sub(r"[_-]+", " ", field_name)
                if field_type == "password" or re.search(
                    r"\b(password|passcode|pin|otp|one.time.code|token|secret|cvv|cvc|card.number)\b",
                    field_name,
                ):
                    raise PermissionError("JARVIS will not enter passwords, PINs, OTPs, tokens, or payment-card secrets. Enter those yourself in the visible browser.")
                if PERSONAL_FIELD_PATTERN.search(field_name):
                    raise PermissionError("JARVIS will not enter personal contact, address, identity, or birth-date details. Enter those yourself in the visible browser.")
                locator.fill(value)
                return "Filled the selected form field. The form was not submitted."
            if action == "select":
                if self._is_financial_context(page, selector):
                    raise PermissionError("Checkout and payment form changes are disabled.")
                if FINANCIAL_LABELS.search(value):
                    raise PermissionError("Selecting checkout or payment options is disabled.")
                if SENSITIVE_LABELS.search(value):
                    details = {"domain": self._host, "action": "click_sensitive_control",
                               "label": value[:240], "selector": selector[:240]}
                    if not callable(approval_callback) or not approval_callback(
                        details, f"Select sensitive website option: {value[:160]}"
                    ):
                        raise PermissionError("Sensitive website selection was not approved.")
                locator.select_option(label=value)
                return "Selected the requested option. The form was not submitted."
            if action == "press":
                key = value.casefold()
                if key in {"enter", "return"}:
                    if self._is_financial_context(page, selector):
                        raise PermissionError("Checkout, cart, and payment form submission is disabled.")
                    field_type = (locator.get_attribute("type") or "").casefold()
                    field_name = " ".join([
                        str(locator.get_attribute("name") or ""),
                        str(locator.get_attribute("aria-label") or ""),
                        selector,
                    ]).casefold()
                    is_search_submit = (
                        field_type == "search"
                        or bool(re.search(r"\b(q|search|query)\b", field_name))
                    )
                    if not is_search_submit:
                        details = {"domain": self._host, "action": "submit_form",
                                   "selector": selector[:240], "key": "Enter"}
                        if not callable(approval_callback) or not approval_callback(
                            details, "Submit the current website form"
                        ):
                            raise PermissionError("Form submission was not approved; the form was not submitted.")
                    locator.press("Enter")
                    return (
                        "Submitted the ordinary search form."
                        if is_search_submit
                        else "Submitted the selected website form after exact one-time voice approval."
                    )
                if key not in {"tab", "escape", "arrowdown", "arrowup", "home", "end"}:
                    raise ValueError("Only navigation keys or approval-gated Enter submission are supported.")
                locator.press(key)
                return f"Pressed {key} on the selected element."
        raise BrowserAutomationError("The browser action did not complete.")

    def status(self) -> dict[str, Any]:
        return self._call_worker("status")

    def close(self):
        if self._worker.is_alive():
            try:
                self._call_worker("close")
            finally:
                self._commands.put(None)

    def _status_local(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._context is not None,
                "domain": self._host,
                "steps_used": self._steps,
                "step_limit": MAX_STEPS_PER_SESSION,
                "profile": "dedicated_jarvis_profile",
                "checkout_and_payments": "disabled",
            }
