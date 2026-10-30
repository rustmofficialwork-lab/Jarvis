import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("jarvis_desktop.py")
SPEC = importlib.util.spec_from_file_location("jarvis_desktop", MODULE_PATH)
jarvis_desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jarvis_desktop)


class ChatCompletionValidationTests(unittest.TestCase):
    def test_rejects_non_https_endpoint(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            jarvis_desktop.chat_completion(
                "http://example.com/v1/chat/completions",
                "model",
                "not-a-real-key",
                "hello",
                [],
            )

    def test_rejects_endpoint_with_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            jarvis_desktop.chat_completion(
                "https://user:password@example.com/v1/chat/completions",
                "model",
                "not-a-real-key",
                "hello",
                [],
            )

    def test_requires_model_and_key(self):
        with self.assertRaisesRegex(ValueError, "model and API key"):
            jarvis_desktop.chat_completion(
                "https://example.com/v1/chat/completions",
                "",
                "",
                "hello",
                [],
            )

class TranscriptTests(unittest.TestCase):
    def test_append_keeps_transcript_when_chat_window_is_closed(self):
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.transcript = []
        app.chat = None
        app._append("YOU", "hello")
        self.assertEqual(app.transcript, [("YOU", "hello", None)])


class ChatHistoryTests(unittest.TestCase):
    def test_history_round_trip_and_bounds(self):
        import tempfile
        path = Path(tempfile.mkdtemp()) / "nested" / "history.json"
        source = [
            {"role": "user", "content": "नमस्ते"},
            {"role": "assistant", "content": "Hello"},
            {"role": "system", "content": "must not persist"},
        ]
        jarvis_desktop.save_chat_history(source, path)
        self.assertEqual(jarvis_desktop.load_chat_history(path), source[:2])

    def test_invalid_history_is_ignored(self):
        import tempfile
        path = Path(tempfile.mkdtemp()) / "history.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(jarvis_desktop.load_chat_history(path), [])

    def test_history_rejects_invalid_roles_and_limits_entries(self):
        import tempfile
        path = Path(tempfile.mkdtemp()) / "history.json"
        path.write_text(__import__("json").dumps(
            [{"role": "system", "content": "no"}] +
            [{"role": "user", "content": str(i)} for i in range(105)]
        ), encoding="utf-8")
        loaded = jarvis_desktop.load_chat_history(path)
        self.assertEqual(len(loaded), 100)
        self.assertEqual(loaded[0]["content"], "5")


if __name__ == "__main__":
    unittest.main()
