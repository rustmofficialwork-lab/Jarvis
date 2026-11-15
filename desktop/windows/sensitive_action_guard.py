"""Exact-scope approval primitives for sensitive JARVIS actions.

This module is a policy layer, not an action executor. It issues short-lived,
single-use approvals bound to an immutable action payload. Real financial
transactions and purchases are deliberately non-executable here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urlsplit

MAX_APPROVAL_TTL_SECONDS = 120
MAX_BROWSER_ACTIONS_PER_SESSION = 20
MAX_BROWSER_DOMAINS_PER_SESSION = 5
BLOCKED_BROWSER_ACTIONS = frozenset({
    "payment", "purchase", "checkout", "send_message", "send_email",
    "change_account", "change_security_settings", "download_executable",
})

# Browser automation is intentionally read-only. Unknown actions fail closed.
ALLOWED_BROWSER_ACTIONS = frozenset({
    "open_page", "read_page", "extract_text", "scroll_page", "click_link",
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
        host = (urlsplit("//" + domain).hostname or "").casefold().rstrip(".")
        if host != domain.casefold().rstrip(".") or not host or "." not in host:
            raise ValueError("Use one exact hostname, not a URL or wildcard.")
        if action.casefold() in BLOCKED_BROWSER_ACTIONS:
            raise PermissionError("This browser action is outside the approved automation scope.")
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
        self._pending: dict[str, ApprovalRequest] = {}
        self._approved: dict[str, tuple[str, float]] = {}

    def request(self, request: ApprovalRequest) -> str:
        if len(self._pending) >= 32:
            raise RuntimeError("Too many pending approval requests; resolve an existing request first.")
        token = secrets.token_urlsafe(24)
        self._pending[token] = request
        return token

    def decide(self, token: str, *, approved: bool) -> ApprovalResult:
        request = self._pending.pop(token, None)
        if request is None:
            return ApprovalResult(False, "invalid_or_used", "Approval request is missing or already used.")
        if self._clock() > request.expires_at:
            return ApprovalResult(False, "expired", "Approval request expired; create a fresh preview.")
        if not approved:
            return ApprovalResult(False, "denied", "The user denied this action.")
        self._approved[request.fingerprint] = (token, request.expires_at)
        return ApprovalResult(True, "approved", "Exact action approved once.")

    def consume(self, action_type: str, details: dict[str, Any]) -> ApprovalResult:
        fingerprint = _canonical_fingerprint(action_type, details)
        grant = self._approved.pop(fingerprint, None)
        if grant is None:
            return ApprovalResult(False, "approval_required", "No approval exists for these exact details.")
        _token, expires_at = grant
        if self._clock() > expires_at:
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
            host = (urlsplit("//" + domain).hostname or "").casefold().rstrip(".")
            if host != domain.casefold().rstrip(".") or not host or "." not in host:
                raise ValueError("Wildcards, paths, and URL schemes are not accepted.")
            normalized.add(host)
        self.allowed_domains = frozenset(normalized)
        self.actions_used = 0

    def authorize(self, domain: str, action: str) -> ApprovalResult:
        if not isinstance(domain, str):
            return ApprovalResult(False, "domain_denied", "Provide one exact hostname.")
        raw_domain = domain.strip().casefold().rstrip(".")
        host = (urlsplit("//" + raw_domain).hostname or "").casefold().rstrip(".")
        # Reject URL schemes, paths, credentials, ports, and other origin syntax.
        if not host or host != raw_domain or host not in self.allowed_domains:
            return ApprovalResult(False, "domain_denied", "This exact hostname is not allowlisted.")
        normalized_action = str(action).strip().casefold()
        if normalized_action in BLOCKED_BROWSER_ACTIONS or normalized_action not in ALLOWED_BROWSER_ACTIONS:
            return ApprovalResult(False, "action_denied", "Only allowlisted read-only browser actions are permitted.")
        if self.actions_used >= MAX_BROWSER_ACTIONS_PER_SESSION:
            return ApprovalResult(False, "limit_reached", "Browser action limit reached for this session.")
        self.actions_used += 1
        return ApprovalResult(True, "allowed", "Domain and bounded action are allowed.")
