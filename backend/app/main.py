from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
from .provider_router import ProviderConfigurationError, ProviderUnavailable, request_with_failover
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status

UPSTREAM_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read a bounded integer setting without making a bad deployment env crash startup."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


MAX_REQUEST_BYTES = _bounded_int_env("MAX_REQUEST_BYTES", 12_582_912, 16_384, 25_165_824)
MAX_UPSTREAM_RESPONSE_BYTES = _bounded_int_env(
    "MAX_UPSTREAM_RESPONSE_BYTES", 2_000_000, 16_384, 8_388_608
)
UPSTREAM_TIMEOUT_SECONDS = _bounded_int_env("UPSTREAM_TIMEOUT_SECONDS", 45, 5, 90)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="JARVIS Backend",
    description="Authenticated AI gateway for the JARVIS desktop assistant.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


DEVICE_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60
REGISTRATION_WINDOW_SECONDS = 60 * 60
REGISTRATION_MAX_ATTEMPTS = 10
CHAT_WINDOW_SECONDS = 60
CHAT_MAX_REQUESTS_PER_WINDOW = 8
CHAT_DAY_SECONDS = 24 * 60 * 60
CHAT_MAX_REQUESTS_PER_DAY = 120
_rate_lock = asyncio.Lock()
_registration_attempts: dict[str, deque[float]] = defaultdict(deque)
_chat_attempts: dict[str, deque[float]] = defaultdict(deque)


def _device_token_secret() -> bytes:
    value = os.getenv("JARVIS_DEVICE_TOKEN_SECRET", "").strip()
    if len(value) < 32:
        return b""
    return value.encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _issue_device_token(device_id: str, now: int | None = None) -> tuple[str, int]:
    secret = _device_token_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Automatic device registration is not configured.",
        )
    issued_at = int(time.time()) if now is None else int(now)
    expires_at = issued_at + DEVICE_TOKEN_TTL_SECONDS
    payload = _b64url(json.dumps({
        "sub": device_id,
        "iat": issued_at,
        "exp": expires_at,
        "iss": "jarvis-backend",
        "aud": "jarvis-desktop",
    }, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
    return f"jdt1.{payload}.{signature}", expires_at


def _verify_device_token(token: str, now: int | None = None) -> str | None:
    secret = _device_token_secret()
    if not secret or len(token) > 4096 or not token.startswith("jdt1."):
        return None
    try:
        prefix, payload_part, signature = token.split(".", 2)
        if prefix != "jdt1":
            return None
        expected = _b64url(hmac.new(
            secret, payload_part.encode("ascii"), hashlib.sha256
        ).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        padded = payload_part + "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        current = int(time.time()) if now is None else int(now)
        if (payload.get("iss") != "jarvis-backend"
                or payload.get("aud") != "jarvis-desktop"
                or not isinstance(payload.get("sub"), str)
                or payload.get("exp", 0) <= current
                or payload.get("iat", current + 1) > current + 60):
            return None
        return payload["sub"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
        return None


async def _read_request_body_limited(
    request: Request, maximum: int, *, detail: str
) -> bytes:
    """Read a request incrementally and stop as soon as its body exceeds the limit.

    Do not use Request.body() here: it buffers the complete body before the
    caller can enforce a limit, which is unsafe for requests without a
    trustworthy Content-Length header (for example, chunked uploads).
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum:
            raise HTTPException(status_code=413, detail=detail)
        chunks.append(chunk)
    return b"".join(chunks)


def _prune_rate_buckets(
    buckets: dict[str, deque[float]], *, now: float, window: int, maximum_keys: int = 10_000
) -> None:
    for key in list(buckets):
        bucket = buckets[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if not bucket:
            buckets.pop(key, None)
    if len(buckets) > maximum_keys:
        excess = len(buckets) - maximum_keys
        for key in list(buckets)[:excess]:
            buckets.pop(key, None)


async def _enforce_window_limit(
    bucket: deque[float], *, now: float, window: int, maximum: int, detail: str
) -> None:
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= maximum:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(max(1, int(window - (now - bucket[0]))))},
        )
    bucket.append(now)


@app.post("/v1/devices/register")
async def register_device(request: Request) -> Response:
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > 512:
                raise HTTPException(status_code=413, detail="Registration request is too large.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length.")
    raw_body = await _read_request_body_limited(
        request, 512, detail="Registration request is too large."
    )
    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    raw_device_id = payload.get("device_id")
    if not isinstance(raw_device_id, str) or len(raw_device_id) > 64:
        raise HTTPException(status_code=422, detail="A valid installation ID is required.")
    try:
        device_id = str(UUID(raw_device_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="A valid installation ID is required.")
    if device_id != raw_device_id.lower():
        raise HTTPException(status_code=422, detail="Installation ID must be a canonical UUID.")

    # Render appends the connecting client address to X-Forwarded-For.
    # Use the last entry (the proxy-appended address), not caller-supplied earlier entries.
    forwarded = request.headers.get("x-forwarded-for", "")
    forwarded_ip = forwarded.rsplit(",", 1)[-1].strip() if forwarded else ""
    client_ip = forwarded_ip or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    async with _rate_lock:
        _prune_rate_buckets(
            _registration_attempts, now=now, window=REGISTRATION_WINDOW_SECONDS
        )
        await _enforce_window_limit(
            _registration_attempts[client_ip],
            now=now,
            window=REGISTRATION_WINDOW_SECONDS,
            maximum=REGISTRATION_MAX_ATTEMPTS,
            detail="Too many device registrations from this network. Try again later.",
        )
    token, expires_at = _issue_device_token(device_id)
    return Response(
        content=json.dumps({"access_token": token, "token_type": "Bearer",
                            "expires_at": expires_at, "expires_in": DEVICE_TOKEN_TTL_SECONDS}),
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def require_client_token(authorization: str | None = Header(default=None)) -> str | None:
    # HTTP authentication scheme names are case-insensitive (RFC 9110).
    parts = authorization.split(None, 1) if authorization else []
    supplied = (
        parts[1].strip()
        if len(parts) == 2 and parts[0].casefold() == "bearer"
        else ""
    )
    if not supplied:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    # Keep existing manually provisioned installations working during migration.
    legacy = os.getenv("JARVIS_CLIENT_TOKEN", "").strip()
    if len(legacy) >= 32 and hmac.compare_digest(supplied, legacy):
        return None

    device_id = _verify_device_token(supplied)
    if device_id is None:
        # Keep authentication failures indistinguishable to unauthenticated callers.
        # A missing signing secret also means the supplied device token cannot be trusted.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials.")
    return device_id


@app.get("/health")
async def health() -> dict[str, str]:
    # Do not expose secret/configuration status in a public health response.
    return {"status": "ok", "service": "jarvis-backend"}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, device_id: str | None = Depends(require_client_token)
) -> Response:
    if device_id is not None:
        now = time.monotonic()
        async with _rate_lock:
            _prune_rate_buckets(_chat_attempts, now=now, window=CHAT_DAY_SECONDS)
            bucket = _chat_attempts[device_id]
            while bucket and bucket[0] <= now - CHAT_DAY_SECONDS:
                bucket.popleft()
            minute_count = sum(1 for stamp in bucket if stamp > now - CHAT_WINDOW_SECONDS)
            if minute_count >= CHAT_MAX_REQUESTS_PER_WINDOW or len(bucket) >= CHAT_MAX_REQUESTS_PER_DAY:
                retry_after = CHAT_WINDOW_SECONDS if minute_count >= CHAT_MAX_REQUESTS_PER_WINDOW else CHAT_DAY_SECONDS
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="JARVIS usage limit reached. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)

    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="Request is too large.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length.")
    raw = await _read_request_body_limited(
        request, MAX_REQUEST_BYTES, detail="Request is too large."
    )
    try:
        payload: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > 60:
        raise HTTPException(status_code=422, detail="Provide between 1 and 60 messages.")
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant", "tool"}:
            raise HTTPException(status_code=422, detail="Invalid chat message.")
    model = payload.get("model") or DEFAULT_MODEL
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise HTTPException(status_code=422, detail="Invalid model name.")
    # Provider endpoints are controlled only by backend environment configuration.
    # The desktop client cannot choose arbitrary upstream URLs or see provider secrets.
    try:
        response_body = await request_with_failover(
            payload,
            timeout=UPSTREAM_TIMEOUT_SECONDS,
            max_response_bytes=MAX_UPSTREAM_RESPONSE_BYTES,
        )
    except ProviderConfigurationError:
        raise HTTPException(status_code=503, detail="AI provider configuration is invalid.")
    except ProviderUnavailable as exc:
        message = str(exc)
        if message == "No AI provider is configured.":
            raise HTTPException(status_code=503, detail="AI provider is not configured.")
        raise HTTPException(status_code=exc.status_code, detail=message)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI provider timed out. Please try again.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="AI provider is temporarily unreachable.")
    return Response(
        content=response_body,
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )

