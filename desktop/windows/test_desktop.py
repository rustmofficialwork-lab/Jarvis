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


if __name__ == "__main__":
    unittest.main()
