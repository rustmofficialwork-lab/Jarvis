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
        # Entering TestClient as a context manager runs FastAPI's lifespan,
        # which initializes the SQLite schema before each test.
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {"Authorization": f"Bearer {os.environ['JARVIS_CLIENT_TOKEN']}"}

    def test_health_is_public_and_minimal(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn("OPENROUTER_API_KEY", response.text)

    def test_memory_requires_authentication(self) -> None:
        response = self.client.get("/v1/memory")
        self.assertEqual(response.status_code, 401)

    def test_memory_can_be_created_listed_and_deleted(self) -> None:
        created = self.client.post(
            "/v1/memory", headers=self.headers, json={"content": "User prefers Hindi replies"}
        )
        self.assertEqual(created.status_code, 201)
        memory_id = created.json()["id"]
        listed = self.client.get("/v1/memory", headers=self.headers)
        self.assertTrue(any(item["id"] == memory_id for item in listed.json()["memories"]))
        deleted = self.client.delete(f"/v1/memory/{memory_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 204)

    def test_invalid_chat_payload_is_rejected_before_upstream_call(self) -> None:
        response = self.client.post(
            "/v1/chat/completions", headers=self.headers, json={"messages": []}
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
