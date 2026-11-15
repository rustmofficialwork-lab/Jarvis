"""Unified orchestration primitives for the JARVIS desktop AI brain.

The engine composes existing policy, memory, and routing components. It does
not execute model-generated code or actions; callers must still use the
allowlisted tool executor and explicit user-consent UI for sensitive actions.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Iterable

from brain_core import ToolDecision, authorize_tool_call, choose_mode
from memory_store import MemoryStore
from sensitive_action_guard import (
    ApprovalLedger, ApprovalRequest, ApprovalResult, BrowserSessionPolicy, build_approval_request,
)


MAX_PLAN_STEPS = 8
MAX_STEP_LENGTH = 240
MAX_FEEDBACK_LENGTH = 500


@dataclass(frozen=True)
class TaskPlan:
    goal: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class TaskEvaluation:
    status: str
    completed: tuple[str, ...]
    remaining: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class Diagnostic:
    category: str
    explanation: str
    next_step: str


def create_task_plan(goal: str, steps: Iterable[str]) -> TaskPlan:
    """Validate a bounded plan supplied by the planner; never invent execution."""
    clean_goal = " ".join(str(goal or "").split())
    if not clean_goal or len(clean_goal) > MAX_STEP_LENGTH:
        raise ValueError("A task goal of 1–240 characters is required.")
    clean_steps: list[str] = []
    for raw in steps:
        step = " ".join(str(raw or "").split())
        if not step:
            continue
        if len(step) > MAX_STEP_LENGTH:
            raise ValueError("Each task step must be 240 characters or fewer.")
        if step not in clean_steps:
            clean_steps.append(step)
        if len(clean_steps) > MAX_PLAN_STEPS:
            raise ValueError(f"A task plan may contain at most {MAX_PLAN_STEPS} steps.")
    if not clean_steps:
        raise ValueError("A task plan must contain at least one step.")
    return TaskPlan(clean_goal, tuple(clean_steps))


def evaluate_task(
    plan: TaskPlan,
    completed_steps: Iterable[str],
    failures: Iterable[str] = (),
) -> TaskEvaluation:
    """Evaluate only explicit step evidence; never infer success from a model claim."""
    completed_set = {
        " ".join(str(item or "").split())
        for item in completed_steps
        if " ".join(str(item or "").split()) in plan.steps
    }
    completed = tuple(step for step in plan.steps if step in completed_set)
    remaining = tuple(step for step in plan.steps if step not in completed_set)
    clean_failures = tuple(
        " ".join(str(item or "").split())[:MAX_STEP_LENGTH]
        for item in failures
        if " ".join(str(item or "").split())
    )[:MAX_PLAN_STEPS]
    if remaining and completed:
        status = "partial"
    elif remaining:
        status = "failed" if clean_failures else "not_started"
    else:
        status = "completed"
    return TaskEvaluation(status, completed, remaining, clean_failures)


def diagnose_failure(error: object) -> Diagnostic:
    """Translate common connectivity/provider failures into actionable guidance."""
    message = str(error or "").strip()
    lowered = message.casefold()
    if any(token in lowered for token in ("timed out", "timeout", "connection refused", "network is unreachable", "urlerror", "name or service not known")):
        return Diagnostic(
            "connectivity",
            "JARVIS could not establish a reliable connection to the requested service.",
            "Check the internet connection and service URL, then retry. Use local AI for supported offline tasks.",
        )
    if any(token in lowered for token in ("401", "403", "unauthorized", "invalid api key", "invalid_credentials")):
        return Diagnostic(
            "authentication",
            "The service rejected its credentials or access permission.",
            "Check the provider key and account permissions in the trusted settings/backend environment; never paste secrets into chat.",
        )
    if any(token in lowered for token in ("429", "rate limit", "rate_limited", "quota")):
        return Diagnostic(
            "rate_limit",
            "The provider is temporarily limiting requests or the configured quota is exhausted.",
            "Wait and retry, or use another configured provider if one is available.",
        )
    if any(token in lowered for token in ("ollama is not installed", "model is not installed", "model not found", "offline model")):
        return Diagnostic(
            "offline_model",
            "The local AI runtime or required model is unavailable.",
            "Install the supported local model while online, then verify that the Ollama service is running.",
        )
    if any(token in lowered for token in ("permission", "access denied", "confirmation_required")):
        return Diagnostic(
            "permission",
            "The requested operation is blocked because the required permission was not granted.",
            "Review the exact action and approve it through JARVIS's trusted confirmation interface if supported.",
        )
    if "404" in lowered or "model_not_found" in lowered:
        return Diagnostic(
            "model_unavailable",
            "The selected provider does not expose the configured model or endpoint.",
            "Verify the provider's current model ID and endpoint, or switch to another configured provider.",
        )
    return Diagnostic(
        "unknown",
        "JARVIS encountered an error it cannot confidently classify.",
        "Keep the error details in the local diagnostic log, check service health, and retry once the cause is understood.",
    )


class BrainEngine:
    """Small coordinator for the core brain policies already used by JARVIS."""

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        # Ephemeral approvals are intentionally lost when JARVIS restarts.
        self.approvals = ApprovalLedger()
        self.browser_session: BrowserSessionPolicy | None = None

    def request_sensitive_approval(
        self, action_type: str, details: dict, summary: str
    ) -> tuple[str, ApprovalRequest]:
        \"\"\"Create an exact-detail preview; this does not execute the action.\"\"\"
        request = build_approval_request(action_type, details, summary)
        return self.approvals.request(request), request

    def decide_sensitive_approval(self, token: str, *, approved: bool) -> ApprovalResult:
        \"\"\"Record a user's decision for one pending, short-lived request.\"\"\"
        return self.approvals.decide(token, approved=approved)

    def consume_sensitive_approval(self, action_type: str, details: dict) -> ApprovalResult:
        \"\"\"Require an exact matching one-time grant before a future executor acts.\"\"\"
        return self.approvals.consume(action_type, details)

    def start_browser_session(self, allowed_domains: list[str]) -> None:
        """Start one bounded, read-only browser session for exact hostnames."""
        self.browser_session = BrowserSessionPolicy(allowed_domains)

    def authorize_browser_action(self, domain: str, action: str) -> ApprovalResult:
        """Authorize one read-only action within the current bounded browser session."""
        if self.browser_session is None:
            return ApprovalResult(False, "session_missing", "No browser domain session has been approved.")
        return self.browser_session.authorize(domain, action)


    @staticmethod
    def select_mode(
        preference: str,
        *,
        internet_available: bool,
        local_model_available: bool,
    ) -> str:
        return choose_mode(
            preference,
            internet_available=internet_available,
            local_model_available=local_model_available,
        )

    @staticmethod
    def authorize(
        tool_name: str,
        arguments: dict,
        user_request: str,
    ) -> ToolDecision:
        return authorize_tool_call(tool_name, arguments, user_request)

    def context_for(self, query: str, *, enabled: bool, limit: int = 5) -> list[str]:
        """Return bounded local memory context only when the caller's privacy setting allows it."""
        if not enabled:
            return []
        limit = max(1, min(int(limit), 10))
        context_method = self.memory.context
        parameters = inspect.signature(context_method).parameters
        accepts_extra = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if "limit" in parameters or accepts_extra:
            items = context_method(query=query, limit=limit)
        else:
            # Keep lightweight adapters and older memory providers compatible.
            items = context_method(query=query)
        return [
            str(item)[:MAX_FEEDBACK_LENGTH]
            for item in items
            if isinstance(item, str) and item.strip()
        ]

    def learn_preference(self, feedback: str, *, explicit: bool) -> dict:
        """Persist only explicitly offered feedback; memory_store rejects secret-like data."""
        if not explicit:
            raise PermissionError("JARVIS can save a preference only after an explicit user request.")
        value = " ".join(str(feedback or "").split())
        if not value or len(value) > MAX_FEEDBACK_LENGTH:
            raise ValueError("Preference feedback must contain 1–500 characters.")
        return self.memory.add(value, "preference")
