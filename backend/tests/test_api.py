import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

_TEMP_DB = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_TEMP_DB.close()
os.environ["DATABASE_PATH"] = _TEMP_DB.name
os.environ["JARVIS_CLIENT_TOKEN"] = "test-token-that-is-long-enough-123456"
os.environ["OPENROUTER_API_KEY"] = "test-upstream-key"

from app.main import app  # noqa: E402


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



if __name__ == "__main__":
    unittest.main()
