"""Exact-scope approval primitives for sensitive JARVIS actions.

This module is a policy layer, not an action executor. It issues short-lived,
single-use approvals bound to an immutable action payload. Real financial
transactions and purchases are deliberately non-executable here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import re
import secrets
import threading
import time
from typing import Any

MAX_APPROVAL_TTL_SECONDS = 120
MAX_BROWSER_ACTIONS_PER_SESSION = 20
MAX_BROWSER_DOMAINS_PER_SESSION = 5
BLOCKED_BROWSER_ACTIONS = frozenset({
    "payment", "purchase", "checkout", "send_message", "send_email",
    "change_account", "change_security_settings", "download_executable",
})

# Browser automation is intentionally read-only. Unknown actions fail closed.
ALLOWED_BROWSER_ACTIONS = frozenset({
    "open_page", "read_page", "extract_text", "scroll_page",
})


@dataclass(frozen=True)
class ApprovalRequest:
    action_type: str
    summary: str
    details_json: str
    fingerprint: str
    expires_at: float

    @property
    def details(self) -> dict[str, Any]:
        # Return a fresh copy so callers cannot mutate the approved preview.
        return json.loads(self.details_json)


@dataclass(frozen=True)
class ApprovalResult:
    approved: bool
    status: str
    reason: str


def _normalize_exact_hostname(domain: str) -> str:
    """Validate a plain DNS hostname; reject IP literals and malformed labels."""
    if not isinstance(domain, str) or not domain or len(domain) > 253:
        raise ValueError("Provide one exact DNS hostname.")
    if domain != domain.strip() or domain.endswith(".") or any(ch.isspace() for ch in domain):
        raise ValueError("Use a hostname only, without whitespace or a trailing dot.")
    host = domain.casefold()
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not accepted as browser allowlist domains.")
    labels = host.split(".")
    if len(labels) < 2 or any(
        not label or len(label) > 63
        or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) is None
        for label in labels
    ):
        raise ValueError("Use a valid exact DNS hostname.")
    return host


def _canonical_fingerprint(action_type: str, details: dict[str, Any]) -> str:
    payload = json.dumps(
        {"action_type": action_type, "details": details},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_approval_request(
    action_type: str, details: dict[str, Any], summary: str, *, now: float | None = None
) -> ApprovalRequest:
    """Build a reviewable request. Required fields are action-specific."""
    if action_type not in {"browser", "email", "message", "payment", "purchase", "delete"}:
        raise ValueError("Unsupported sensitive action type.")
    if not isinstance(details, dict) or not isinstance(summary, str) or not summary.strip():
        raise ValueError("A clear summary and structured action details are required.")
    required = {
        "browser": ("domain", "action"),
        "email": ("recipient", "subject", "content"),
        "message": ("recipient", "content"),
        "payment": ("amount", "currency", "recipient", "purpose"),
        "purchase": ("product", "price", "currency", "order"),
        "delete": ("paths", "recovery"),
    }[action_type]
    if any(key not in details for key in required):
        raise ValueError("The approval preview is missing required action details.")
    if action_type in {"email", "message"}:
        if not all(isinstance(details[key], str) and details[key].strip() for key in required):
            raise ValueError("Recipient and final message content must be shown before approval.")
    if action_type == "payment":
        amount = details["amount"]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Payment amount must be a positive number.")
        if not all(isinstance(details[key], str) and details[key].strip()
                   for key in ("currency", "recipient", "purpose")):
            raise ValueError("Payment recipient, currency, and purpose must be explicit.")
    if action_type == "purchase":
        if not all(isinstance(details[key], str) and details[key].strip()
                   for key in ("product", "currency", "order")):
            raise ValueError("Product, currency, and order details must be explicit.")
        price = details["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise ValueError("Purchase price must be a positive number.")
    if action_type == "delete":
        paths = details["paths"]
        if not isinstance(paths, list) or not paths or len(paths) > 20:
            raise ValueError("Select between 1 and 20 exact files.")
        if any(not isinstance(path, str) or not path.strip() for path in paths):
            raise ValueError("Every selected file path must be explicit.")
        if details["recovery"] is not True:
            raise ValueError("Deletion must use a recoverable recycle-bin/trash operation.")
    if action_type == "browser":
        domain = details["domain"]
        action = details["action"]
        if (not isinstance(domain, str) or not isinstance(action, str)
                or not action.strip()):
            raise ValueError("Browser domain and requested action are required.")
        host = _normalize_exact_hostname(domain)
        normalized_action = action.strip().casefold()
        if normalized_action in BLOCKED_BROWSER_ACTIONS or normalized_action not in ALLOWED_BROWSER_ACTIONS:
            raise PermissionError("Only explicitly allowlisted read-only browser actions can be approved.")
    current = time.time() if now is None else now
    safe_details = json.loads(json.dumps(details, sort_keys=True))
    return ApprovalRequest(
        action_type=action_type,
        summary=summary.strip()[:240],
        details_json=json.dumps(safe_details, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        fingerprint=_canonical_fingerprint(action_type, safe_details),
        expires_at=current + MAX_APPROVAL_TTL_SECONDS,
    )


class ApprovalLedger:
    """In-memory, one-use approvals. Restarting JARVIS invalidates every approval."""

    def __init__(self, *, clock=time.time):
        self._clock = clock
        self._lock = threading.RLock()
        self._pending: dict[str, ApprovalRequest] = {}
        self._approved: dict[str, tuple[str, float]] = {}

    def _purge_expired(self, now: float) -> None:
        """Drop stale requests and grants so abandoned approvals cannot exhaust the ledger."""
        self._pending = {
            token: request for token, request in self._pending.items()
            if request.expires_at > now
        }
        self._approved = {
            fingerprint: grant for fingerprint, grant in self._approved.items()
            if grant[1] > now
        }

    def request(self, request: ApprovalRequest) -> str:
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            if request.expires_at <= now:
                raise ValueError("Cannot queue an approval request that has already expired.")
            if len(self._pending) >= 32:
                raise RuntimeError("Too many pending approval requests; resolve an existing request first.")
            token = secrets.token_urlsafe(24)
            self._pending[token] = request
            return token

    def decide(self, token: str, *, approved: bool) -> ApprovalResult:
        with self._lock:
            now = self._clock()
            # Pop the requested token before sweeping so its caller receives the
            # precise "expired" result rather than an ambiguous missing-token result.
            request = self._pending.pop(token, None)
            self._purge_expired(now)
            if request is None:
                return ApprovalResult(False, "invalid_or_used", "Approval request is missing or already used.")
            if request.expires_at <= now:
                return ApprovalResult(False, "expired", "Approval request expired; create a fresh preview.")
            if not approved:
                return ApprovalResult(False, "denied", "The user denied this action.")
            self._approved[request.fingerprint] = (token, request.expires_at)
            return ApprovalResult(True, "approved", "Exact action approved once.")

    def consume(self, action_type: str, details: dict[str, Any]) -> ApprovalResult:
        fingerprint = _canonical_fingerprint(action_type, details)
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            grant = self._approved.pop(fingerprint, None)
            if grant is None:
                return ApprovalResult(False, "approval_required", "No approval exists for these exact details.")
            _token, expires_at = grant
            if expires_at <= now:
                return ApprovalResult(False, "expired", "Approval expired; request approval again.")
            return ApprovalResult(True, "approved", "Exact one-time approval consumed.")


class BrowserSessionPolicy:
    """Per-session domain/action budget; only exact domains can be allowlisted."""

    def __init__(self, allowed_domains: list[str]):
        if not isinstance(allowed_domains, list) or not 1 <= len(allowed_domains) <= MAX_BROWSER_DOMAINS_PER_SESSION:
            raise ValueError("Allow between 1 and 5 exact domains.")
        normalized = set()
        for domain in allowed_domains:
            if not isinstance(domain, str):
                raise ValueError("Domains must be exact hostnames.")
            normalized.add(_normalize_exact_hostname(domain))
        self.allowed_domains = frozenset(normalized)
        self.actions_used = 0
        self._lock = threading.Lock()

    def authorize(self, domain: str, action: str) -> ApprovalResult:
        if not isinstance(domain, str):
            return ApprovalResult(False, "domain_denied", "Provide one exact hostname.")
        # Reject URL schemes, paths, credentials, ports, IP literals, and malformed DNS labels.
        try:
            host = _normalize_exact_hostname(domain)
        except ValueError:
            return ApprovalResult(False, "domain_denied", "Provide one valid exact DNS hostname.")
        if host not in self.allowed_domains:
            return ApprovalResult(False, "domain_denied", "This exact hostname is not allowlisted.")
        if not isinstance(action, str):
            return ApprovalResult(False, "action_denied", "Only allowlisted read-only browser actions are permitted.")
        normalized_action = action.strip().casefold()
        if normalized_action in BLOCKED_BROWSER_ACTIONS or normalized_action not in ALLOWED_BROWSER_ACTIONS:
            return ApprovalResult(False, "action_denied", "Only allowlisted read-only browser actions are permitted.")
        # The budget check and increment must be atomic when multiple tool calls
        # arrive concurrently from voice, chat, or background workers.
        with self._lock:
            if self.actions_used >= MAX_BROWSER_ACTIONS_PER_SESSION:
                return ApprovalResult(False, "limit_reached", "Browser action limit reached for this session.")
            self.actions_used += 1
            return ApprovalResult(True, "allowed", "Domain and bounded action are allowed.")
