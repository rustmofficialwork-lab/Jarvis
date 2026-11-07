import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

_TEMP_DB = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_TEMP_DB.close()
os.environ["DATABASE_PATH"] = _TEMP_DB.name
os.environ["JARVIS_CLIENT_TOKEN"] = "test-token-that-is-long-enough-123456"
os.environ["OPENROUTER_API_KEY"] = "test-upstream-key"

from app.main import UPSTREAM_URL, app  # noqa: E402


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

    def test_chat_requires_a_valid_bearer_token(self) -> None:
        payload = {"model": "openrouter/free", "messages": [{"role": "user", "content": "hi"}]}
        for headers in ({}, {"Authorization": "Bearer wrong-token"}):
            with self.subTest(headers=headers):
                response = self.client.post("/v1/chat/completions", headers=headers, json=payload)
                self.assertEqual(response.status_code, 401)

    def test_shared_memory_api_is_not_exposed(self) -> None:
        response = self.client.get("/v1/memory", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_invalid_chat_payload_is_rejected_before_upstream_call(self) -> None:
        response = self.client.post(
            "/v1/chat/completions", headers=self.headers, json={"messages": []}
        )
        self.assertEqual(response.status_code, 422)

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
