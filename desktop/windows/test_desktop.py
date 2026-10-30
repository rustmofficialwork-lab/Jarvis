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


class LocalCommandHistoryTests(unittest.TestCase):
    def test_failed_local_action_is_visible_and_persisted(self):
        from unittest.mock import patch
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.history = []
        app.transcript = []
        app.chat = None
        app._set_status = lambda _text: None
        with patch.object(jarvis_desktop, "run_local_command",
                          side_effect=RuntimeError("test failure")), \
             patch.object(jarvis_desktop, "save_chat_history") as save:
            self.assertTrue(app._try_local_command("open notepad"))
        self.assertEqual([item["role"] for item in app.history], ["user", "assistant"])
        self.assertEqual(app.history[0]["content"], "open notepad")
        self.assertIn("test failure", app.history[1]["content"])
        self.assertEqual([item[0] for item in app.transcript], ["YOU", "JARVIS ERROR"])
        save.assert_called_once_with(app.history)


class LocalCommandTests(unittest.TestCase):
    def test_allowlisted_app_uses_shell_false(self):
        calls = []
        result = jarvis_desktop.run_local_command(
            "  OPEN   NOTEPAD! ",
            popen=lambda args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertEqual(result, "Opening Notepad.")
        self.assertEqual(calls, [(["notepad.exe"], {"shell": False})])

    def test_allowlisted_website_uses_fixed_url(self):
        opened = []
        result = jarvis_desktop.run_local_command(
            "open youtube", open_url=lambda url: opened.append(url) or True,
        )
        self.assertEqual(result, "Opening YouTube.")
        self.assertEqual(opened, ["https://www.youtube.com"])

    def test_unknown_or_injected_commands_are_not_executed(self):
        calls = []
        result = jarvis_desktop.run_local_command(
            "open notepad & del important.txt",
            popen=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertIsNone(result)
        self.assertEqual(calls, [])


class ServiceStatusTests(unittest.TestCase):
    def test_service_status_does_not_claim_unconfigured_ai_or_voice_ready(self):
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.ai_api_key = ""
        app.picovoice_access_key = ""
        statuses = app._get_service_statuses()
        by_name = {name: ready for name, ready, _detail in statuses}
        self.assertFalse(by_name["AI CHAT"])
        self.assertFalse(by_name["VOICE ENGINE"])
        self.assertTrue(by_name["MEMORY"])
        self.assertEqual(len(statuses), 4)

    def test_configured_ai_and_voice_readiness_uses_installed_packages(self):
        from unittest.mock import patch
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.ai_api_key = "test-token"
        app.picovoice_access_key = "test-key"
        with patch("importlib.util.find_spec", return_value=object()):
            statuses = app._get_service_statuses()
        by_name = {name: ready for name, ready, _detail in statuses}
        self.assertTrue(by_name["AI CHAT"])
        self.assertTrue(by_name["VOICE ENGINE"])


class WindowsMediaKeyTests(unittest.TestCase):
    def test_volume_and_media_actions_emit_fixed_key_down_and_up(self):
        calls = []
        sent = jarvis_desktop.press_windows_media_key(
            "volume_up", keybd_event=lambda *args: calls.append(args), platform_name="nt",
        )
        self.assertTrue(sent)
        self.assertEqual(calls, [(0xAF, 0, 0, 0), (0xAF, 0, 2, 0)])

    def test_unknown_key_and_non_windows_are_rejected(self):
        calls = []
        self.assertFalse(jarvis_desktop.press_windows_media_key(
            "arbitrary_key", keybd_event=lambda *args: calls.append(args), platform_name="nt",
        ))
        self.assertFalse(jarvis_desktop.press_windows_media_key(
            "volume_up", keybd_event=lambda *args: calls.append(args), platform_name="posix",
        ))
        self.assertEqual(calls, [])

    def test_voice_command_mapping_only_accepts_fixed_media_phrases(self):
        from unittest.mock import patch
        with patch.object(jarvis_desktop, "press_windows_media_key", return_value=True) as press:
            self.assertEqual(jarvis_desktop.run_local_command("volume up"), "Volume increased.")
            self.assertEqual(jarvis_desktop.run_local_command("next track"), "Skipping to the next track.")
            self.assertIsNone(jarvis_desktop.run_local_command("run powershell"))
        self.assertEqual([call.args[0] for call in press.call_args_list], ["volume_up", "next_track"])


class WindowsPowerActionTests(unittest.TestCase):
    def test_shutdown_restart_and_cancel_use_fixed_safe_commands(self):
        calls = []
        for action, expected in [
            ("shutdown", ["shutdown.exe", "/s", "/t", "60"]),
            ("restart", ["shutdown.exe", "/r", "/t", "60"]),
            ("cancel", ["shutdown.exe", "/a"]),
        ]:
            self.assertTrue(jarvis_desktop.schedule_windows_power_action(
                action, popen=lambda command, **kwargs: calls.append((command, kwargs)),
                platform_name="nt",
            ))
            self.assertEqual(calls[-1], (expected, {"shell": False}))

    def test_unknown_or_non_windows_power_actions_are_rejected(self):
        calls = []
        self.assertFalse(jarvis_desktop.schedule_windows_power_action(
            "format_disk", popen=lambda *args, **kwargs: calls.append(args), platform_name="nt",
        ))
        self.assertFalse(jarvis_desktop.schedule_windows_power_action(
            "shutdown", popen=lambda *args, **kwargs: calls.append(args), platform_name="posix",
        ))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
