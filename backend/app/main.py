from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

UPSTREAM_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
MAX_REQUEST_BYTES = max(16_384, int(os.getenv("MAX_REQUEST_BYTES", "12582912")))
UPSTREAM_TIMEOUT_SECONDS = max(5, min(90, int(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "45"))))


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="JARVIS Backend",
    description="Private AI gateway and persistent memory API for the JARVIS assistant.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


def require_client_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("JARVIS_CLIENT_TOKEN", "").strip()
    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend client authentication is not configured.",
        )
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")


@app.get("/health")
async def health() -> dict[str, str]:
    # Do not expose secret/configuration status in a public health response.
    return {"status": "ok", "service": "jarvis-backend"}


@app.post("/v1/chat/completions", dependencies=[Depends(require_client_token)])
async def chat_completions(request: Request) -> Response:
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="Request is too large.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length.")
    raw = await request.body()
    if len(raw) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Request is too large.")
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
    # Keep the upstream destination fixed to avoid turning this service into an open proxy.
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="AI provider is not configured.")
    payload["model"] = model
    payload["stream"] = False
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://github.com/rustmofficialwork-lab/Jarvis"),
        "X-Title": "JARVIS Assistant",
    }
    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
            upstream = await client.post(UPSTREAM_URL, headers=headers, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI provider timed out. Please try again.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="AI provider is temporarily unreachable.")
    if upstream.status_code == 429:
        raise HTTPException(status_code=429, detail="AI provider rate limit reached. Try again shortly.")
    if upstream.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="AI provider credentials were rejected.")
    if upstream.status_code >= 500:
        raise HTTPException(status_code=502, detail="AI provider is temporarily unavailable.")
    if upstream.status_code >= 400:
        # Do not relay upstream headers or internal details.
        raise HTTPException(status_code=502, detail="AI provider rejected the request.")
    return Response(
        content=upstream.content,
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )

