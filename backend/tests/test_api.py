import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

_TEMP_DB = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_TEMP_DB.close()
os.environ["DATABASE_PATH"] = _TEMP_DB.name
os.environ["JARVIS_CLIENT_TOKEN"] = "test-token-that-is-long-enough-123456"
os.environ["OPENROUTER_API_KEY"] = "test-upstream-key"
os.environ["JARVIS_DEVICE_TOKEN_SECRET"] = "test-device-token-secret-that-is-long-enough-123"

from app.main import (  # noqa: E402
    UPSTREAM_URL, _chat_attempts, _legacy_chat_attempts, _b64url,
    _read_request_body_limited, _verify_device_token, app, require_client_token,
)


class _FakeUpstreamResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def aiter_bytes(self):
        yield self.body


class _FakeAsyncClient:
    status_code = 200
    response_body = b'{"choices":[{"message":{"role":"assistant","content":"Hello from JARVIS"}}]}'
    captured = {}

    def __init__(self, *args, **kwargs):
        self.captured = {"client_kwargs": kwargs}
        type(self).captured = self.captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method, url, *, headers, json):
        self.captured.update({
            "method": method,
            "url": url,
            "headers": headers,
            "payload": json,
        })
        return _FakeUpstreamResponse(type(self).status_code, type(self).response_body)


class _ChunkedRequest:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.consumed = 0

    async def stream(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk


class RequestBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_streamed_body_within_limit_is_returned(self):
        request = _ChunkedRequest([b"hello", b" ", b"world"])
        body = await _read_request_body_limited(request, 11, detail="too large")
        self.assertEqual(body, b"hello world")
        self.assertEqual(request.consumed, 3)

    async def test_streamed_body_without_content_length_is_rejected_early(self):
        request = _ChunkedRequest([b"123", b"456", b"must-not-be-read"])
        with self.assertRaises(HTTPException) as raised:
            await _read_request_body_limited(request, 5, detail="too large")
        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(raised.exception.detail, "too large")
        self.assertEqual(request.consumed, 2)

    async def test_empty_stream_is_allowed_by_body_reader(self):
        request = _ChunkedRequest([])
        body = await _read_request_body_limited(request, 5, detail="too large")
        self.assertEqual(body, b"")
        self.assertEqual(request.consumed, 0)


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        # Entering TestClient as a context manager runs FastAPI lifespan hooks.
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {"Authorization": f"Bearer {os.environ['JARVIS_CLIENT_TOKEN']}"}

    def test_health_is_public_and_minimal(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn("OPENROUTER_API_KEY", response.text)

    def test_legacy_shared_token_is_rate_limited_by_peer_ip(self) -> None:
        peer_ip = "testclient"
        now = time.monotonic()
        _legacy_chat_attempts[peer_ip].clear()
        _legacy_chat_attempts[peer_ip].extend([now - 1] * 30)
        self.addCleanup(_legacy_chat_attempts.pop, peer_ip, None)
        response = self.client.post(
            "/v1/chat/completions",
            headers=self.headers,
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        self.assertEqual(response.status_code, 429, response.text)
        self.assertIn("Retry-After", response.headers)

    def test_chat_requires_a_valid_bearer_token(self) -> None:
        payload = {"model": "openrouter/free", "messages": [{"role": "user", "content": "hi"}]}
        for headers in ({}, {"Authorization": "Bearer wrong-token"}):
            with self.subTest(headers=headers):
                response = self.client.post("/v1/chat/completions", headers=headers, json=payload)
                self.assertEqual(response.status_code, 401)

    def test_bearer_scheme_is_case_insensitive(self) -> None:
        token = os.environ["JARVIS_CLIENT_TOKEN"]
        for scheme in ("Bearer", "bearer", "BEARER", "bEaReR"):
            with self.subTest(scheme=scheme):
                self.assertIsNone(require_client_token(f"{scheme} {token}"))

    def test_non_bearer_authentication_scheme_is_rejected(self) -> None:
        for authorization in ("Basic some-token", "Bearer", "Bearer   "):
            with self.subTest(authorization=authorization):
                with self.assertRaises(HTTPException) as raised:
                    require_client_token(authorization)
                self.assertEqual(raised.exception.status_code, 401)

    def test_device_registration_issues_signed_short_lived_token(self) -> None:
        device_id = str(uuid.uuid4())
        response = self.client.post("/v1/devices/register", json={"device_id": device_id})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        body = response.json()
        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["expires_in"], 30 * 24 * 60 * 60)
        self.assertGreater(body["expires_at"], 0)
        token = body["access_token"]
        self.assertTrue(token.startswith("jdt1."))
        self.assertEqual(len(token.split(".")), 3)

    def test_device_registration_rejects_invalid_installation_ids(self) -> None:
        for device_id in ("", "not-a-uuid", 123, None):
            with self.subTest(device_id=device_id):
                response = self.client.post(
                    "/v1/devices/register", json={"device_id": device_id}
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_registered_device_token_authenticates_chat_request(self) -> None:
        device_id = str(uuid.uuid4())
        registration = self.client.post(
            "/v1/devices/register", json={"device_id": device_id}
        )
        self.assertEqual(registration.status_code, 200, registration.text)
        token = registration.json()["access_token"]
        _FakeAsyncClient.status_code = 200
        _FakeAsyncClient.response_body = (
            b'{"choices":[{"message":{"role":"assistant","content":"Device authenticated"}}]}'
        )
        with patch("app.main.httpx.AsyncClient", _FakeAsyncClient):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": "openrouter/free",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["choices"][0]["message"]["content"],
            "Device authenticated",
        )

    def test_device_token_verifier_rejects_malformed_signed_claims(self) -> None:
        secret = os.environ["JARVIS_DEVICE_TOKEN_SECRET"].encode("utf-8")
        valid_id = str(uuid.uuid4())
        cases = (
            [],
            {"sub": valid_id, "iat": "1", "exp": int(time.time()) + 60,
             "iss": "jarvis-backend", "aud": "jarvis-desktop"},
            {"sub": "not-a-uuid", "iat": int(time.time()), "exp": int(time.time()) + 60,
             "iss": "jarvis-backend", "aud": "jarvis-desktop"},
            {"sub": valid_id, "iat": int(time.time()), "exp": "later",
             "iss": "jarvis-backend", "aud": "jarvis-desktop"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                encoded = _b64url(json.dumps(payload).encode("utf-8"))
                signature = _b64url(
                    hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).digest()
                )
                self.assertIsNone(_verify_device_token(f"jdt1.{encoded}.{signature}"))

    def test_device_token_verifier_rejects_non_ascii_token_without_crashing(self) -> None:
        self.assertIsNone(_verify_device_token("jdt1.é.signature"))

    def test_tampered_device_token_is_rejected(self) -> None:
        device_id = str(uuid.uuid4())
        registration = self.client.post(
            "/v1/devices/register", json={"device_id": device_id}
        )
        self.assertEqual(registration.status_code, 200, registration.text)
        token = registration.json()["access_token"]
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        response = self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {tampered}"},
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_shared_memory_api_is_not_exposed(self) -> None:
        response = self.client.get("/v1/memory", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_invalid_chat_payload_is_rejected_before_upstream_call(self) -> None:
        response = self.client.post(
            "/v1/chat/completions", headers=self.headers, json={"messages": []}
        )
        self.assertEqual(response.status_code, 422)

    def test_deeply_nested_chat_json_is_rejected_without_server_error(self) -> None:
        nested = b'{"messages":' + (b"[" * 1100) + b"0" + (b"]" * 1100) + b"}"
        response = self.client.post(
            "/v1/chat/completions",
            headers={**self.headers, "Content-Type": "application/json"},
            content=nested,
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_non_object_chat_json_is_rejected_without_server_error(self) -> None:
        for payload in ([], ["messages"], "hello", 42, None):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/v1/chat/completions",
                    headers={**self.headers, "Content-Type": "application/json"},
                    content=json.dumps(payload),
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_chat_forwards_authenticated_request_and_returns_provider_reply(self) -> None:
        _FakeAsyncClient.status_code = 200
        _FakeAsyncClient.response_body = (
            b'{"choices":[{"message":{"role":"assistant","content":"Hello from JARVIS"}}]}'
        )
        with patch("app.main.httpx.AsyncClient", _FakeAsyncClient):
            response = self.client.post(
                "/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "openrouter/free",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["choices"][0]["message"]["content"], "Hello from JARVIS")
        self.assertEqual(_FakeAsyncClient.captured["method"], "POST")
        self.assertEqual(_FakeAsyncClient.captured["url"], UPSTREAM_URL)
        self.assertEqual(
            _FakeAsyncClient.captured["headers"]["Authorization"],
            "Bearer test-upstream-key",
        )
        self.assertEqual(_FakeAsyncClient.captured["payload"]["model"], "openrouter/free")
        self.assertFalse(_FakeAsyncClient.captured["payload"]["stream"])

    def test_chat_maps_provider_failures_to_safe_gateway_errors(self) -> None:
        cases = (
            (429, 429, "AI provider rate limit reached."),
            (401, 502, "AI provider credentials were rejected."),
            (503, 502, "AI provider is temporarily unavailable."),
            (400, 502, "AI provider rejected the request."),
        )
        for upstream_status, expected_status, expected_detail in cases:
            with self.subTest(upstream_status=upstream_status):
                _FakeAsyncClient.status_code = upstream_status
                _FakeAsyncClient.response_body = b'{"error":"provider detail"}'
                with patch("app.main.httpx.AsyncClient", _FakeAsyncClient):
                    response = self.client.post(
                        "/v1/chat/completions",
                        headers=self.headers,
                        json={
                            "model": "openrouter/free",
                            "messages": [{"role": "user", "content": "Hello"}],
                        },
                    )
                self.assertEqual(response.status_code, expected_status)
                self.assertIn(expected_detail, response.json()["detail"])
                self.assertNotIn("provider detail", response.text)


if __name__ == "__main__":
    unittest.main()
