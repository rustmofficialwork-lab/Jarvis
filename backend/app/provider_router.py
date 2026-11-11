"""Configurable failover across OpenAI-compatible AI providers.

Provider configuration is supplied only by the backend environment:
JARVIS_AI_PROVIDERS='[{"name":"primary","base_url":"https://.../chat/completions","api_key_env":"PRIMARY_API_KEY","model":"..."}]'
Keys are never returned to clients or written to logs. If the variable is absent,
the legacy OpenRouter configuration remains the default.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
import re
from urllib.parse import urlsplit

import httpx

DEFAULT_UPSTREAM_URL = "https://openrouter.ai/api/v1/chat/completions"
# 404 is common when a configured model is not available on a provider. Treat it
# as provider-specific unavailability and allow the next configured provider a try.
RETRYABLE_STATUS_CODES = {404, 408, 425, 429}
MAX_CONFIGURED_PROVIDERS = 5
_ENV_VAR_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


class ProviderConfigurationError(Exception):
    pass


class ProviderUnavailable(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _valid_provider_url(url: str) -> bool:
    """Accept only well-formed HTTPS endpoints without URL-embedded credentials."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == ""
        and (port is None or 1 <= port <= 65535)
    )


def _is_chat_completion_response(body: bytes) -> bool:
    """Reject malformed/non-chat success bodies so a healthy fallback can answer."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    message = first.get("message")
    if not isinstance(message, dict):
        return False
    # A syntactically valid JSON object with an empty message is not a usable
    # completion. Tool-call-only and refusal responses remain valid.
    return (
        message.get("role") in (None, "assistant")
        and any(key in message for key in ("content", "tool_calls", "refusal"))
    )


def load_providers(environ: dict[str, str] | None = None) -> list[Provider]:
    """Load ordered providers; preserve the existing OpenRouter-only setup."""
    env = os.environ if environ is None else environ
    raw = env.get("JARVIS_AI_PROVIDERS", "").strip()
    entries: list[dict[str, Any]]
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderConfigurationError("JARVIS_AI_PROVIDERS must be valid JSON.") from exc
        if not isinstance(parsed, list) or not parsed:
            raise ProviderConfigurationError("JARVIS_AI_PROVIDERS must be a non-empty JSON array.")
        entries = parsed
    else:
        entries = [{
            "name": "openrouter",
            "base_url": DEFAULT_UPSTREAM_URL,
            "api_key_env": "OPENROUTER_API_KEY",
            "model": env.get("OPENROUTER_MODEL", "openrouter/free"),
        }]

    providers: list[Provider] = []
    provider_names: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ProviderConfigurationError("Each AI provider entry must be an object.")
        name = item.get("name")
        url = item.get("base_url")
        key_env = item.get("api_key_env")
        model = item.get("model")
        if not all(isinstance(value, str) and value.strip() for value in (name, url, key_env, model)):
            raise ProviderConfigurationError(f"AI provider entry {index + 1} is missing required fields.")
        url = url.strip()
        if len(url) > 500 or not _valid_provider_url(url):
            raise ProviderConfigurationError(
                f"AI provider entry {index + 1} must use a valid HTTPS endpoint without embedded credentials."
            )
        name = name.strip()
        key_env = key_env.strip()
        model = model.strip()
        if len(name) > 64 or len(key_env) > 128 or len(model) > 200:
            raise ProviderConfigurationError(f"AI provider entry {index + 1} contains an oversized setting.")
        if not _ENV_VAR_NAME.fullmatch(key_env):
            raise ProviderConfigurationError(
                f"AI provider entry {index + 1} has an invalid API-key environment variable name."
            )
        if name.casefold() in provider_names:
            raise ProviderConfigurationError("AI provider names must be unique.")
        provider_names.add(name.casefold())
        key = env.get(key_env, "").strip()
        if key:
            providers.append(Provider(name=name, base_url=url, api_key=key, model=model))
    return providers


async def request_with_failover(
    payload: dict[str, Any],
    *,
    timeout: int,
    max_response_bytes: int,
    environ: dict[str, str] | None = None,
    client_factory=None,
) -> bytes:
    """Try configured providers in order and return the first bounded valid response."""
    providers = load_providers(environ)
    # Resolve at call time so tests and application-level HTTP client overrides work.
    make_client = client_factory or httpx.AsyncClient
    if not providers:
        raise ProviderUnavailable("No AI provider is configured.")
    failures: list[str] = []
    for provider in providers:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        body = dict(payload)
        body["model"] = provider.model
        body["stream"] = False
        try:
            async with make_client(timeout=timeout) as client:
                async with client.stream("POST", provider.base_url, headers=headers, json=body) as response:
                    status_code = response.status_code
                    if status_code >= 400:
                        if status_code == 429:
                            failures.append("rate-limited")
                            continue
                        if status_code in (401, 403):
                            failures.append("auth-rejected")
                            continue
                        if status_code in RETRYABLE_STATUS_CODES or status_code >= 500:
                            failures.append("temporarily-unavailable")
                            continue
                        raise ProviderUnavailable("The AI provider rejected the request.")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_response_bytes:
                            failures.append("response-too-large")
                            break
                        chunks.append(chunk)
                    else:
                        result = b"".join(chunks)
                        if _is_chat_completion_response(result):
                            return result
                        failures.append("invalid-response")
                    continue
        except httpx.TimeoutException:
            failures.append("timeout")
        except httpx.RequestError:
            failures.append("network-error")
    if failures and all(reason == "rate-limited" for reason in failures):
        raise ProviderUnavailable("AI provider rate limit reached.", status_code=429)
    if failures and all(reason == "auth-rejected" for reason in failures):
        raise ProviderUnavailable("AI provider credentials were rejected.")
    if failures and all(reason in {"temporarily-unavailable", "timeout", "network-error", "response-too-large", "invalid-response"} for reason in failures):
        raise ProviderUnavailable("AI provider is temporarily unavailable.")
    raise ProviderUnavailable("All configured AI providers are temporarily unavailable.")
