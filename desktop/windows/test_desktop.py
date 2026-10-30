import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("jarvis_desktop.py")
SPEC = importlib.util.spec_from_file_location("jarvis_desktop", MODULE_PATH)
jarvis_desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jarvis_desktop)


class InterruptibleSpeechTests(unittest.TestCase):
    def test_speech_finishes_when_engine_becomes_idle(self):
        class FakeEngine:
            def __init__(self):
                self.busy_checks = 0
                self.ended = False
            def say(self, text):
                self.text = text
            def startLoop(self, use_driver_loop):
                self.started = use_driver_loop
            def isBusy(self):
                self.busy_checks += 1
                return self.busy_checks == 1
            def iterate(self):
                pass
            def endLoop(self):
                self.ended = True
            def stop(self):
                pass
        engine = FakeEngine()
        import threading
        self.assertTrue(jarvis_desktop.speak_text_interruptibly(
            "Hello", threading.Event(), engine_factory=lambda: engine,
        ))
        self.assertTrue(engine.ended)
        self.assertEqual(engine.text, "Hello")

    def test_stop_request_interrupts_speech(self):
        class FakeEngine:
            def __init__(self):
                self.stop_event = None
                self.stopped = False
            def say(self, text):
                pass
            def startLoop(self, use_driver_loop):
                pass
            def isBusy(self):
                return True
            def iterate(self):
                self.stop_event.set()
            def endLoop(self):
                pass
            def stop(self):
                self.stopped = True
        import threading
        event = threading.Event()
        engine = FakeEngine()
        engine.stop_event = event
        self.assertFalse(jarvis_desktop.speak_text_interruptibly(
            "Long response", event, engine_factory=lambda: engine,
        ))
        self.assertTrue(engine.stopped)


    def test_voice_local_command_speaks_confirmation_and_persists_history(self):
        from unittest.mock import patch
        import queue
        import threading
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.events = queue.Queue()
        app.history = []
        app.request_lock = threading.Lock()
        app.speech_stop_event = threading.Event()
        app.speech_stop_event.set()
        with (
            patch.object(jarvis_desktop, "run_local_command", return_value="Opening Notepad."),
            patch.object(jarvis_desktop, "save_chat_history") as save,
            patch.object(jarvis_desktop, "speak_text_interruptibly") as speak,
        ):
            app._answer_voice("open notepad")
        self.assertFalse(app.speech_stop_event.is_set())
        speak.assert_called_once_with("Opening Notepad.", app.speech_stop_event)
        save.assert_called_once_with(app.history)
        self.assertEqual([item["role"] for item in app.history], ["user", "assistant"])
        self.assertFalse(app.request_lock.locked())

    def test_voice_request_does_not_run_local_action_while_another_request_owns_lock(self):
        from unittest.mock import patch
        import queue
        import threading
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.events = queue.Queue()
        app.history = []
        app.request_lock = threading.Lock()
        app.request_lock.acquire()
        app.speech_stop_event = threading.Event()
        with patch.object(jarvis_desktop, "run_local_command") as local:
            app._answer_voice("open notepad")
        local.assert_not_called()
        app.request_lock.release()

    def test_voice_reply_uses_interruptible_speech(self):
        from unittest.mock import patch
        import queue
        import threading
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.events = queue.Queue()
        app.settings = {"endpoint": "https://example.com/chat", "model": "test-model"}
        app.ai_api_key = "test-key"
        app.history = []
        app.request_lock = threading.Lock()
        app.speech_stop_event = threading.Event()
        with (
            patch.object(jarvis_desktop, "chat_completion", return_value="Namaste"),
            patch.object(jarvis_desktop, "save_chat_history"),
            patch.object(jarvis_desktop, "speak_text_interruptibly", return_value=True) as speak,
        ):
            app._answer_voice("hello JARVIS")
        speak.assert_called_once_with("Namaste", app.speech_stop_event)
        self.assertEqual([item["role"] for item in app.history], ["user", "assistant"])

    def test_stop_requested_during_voice_generation_is_not_cleared_before_speech(self):
        from unittest.mock import patch
        import queue
        import threading
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.events = queue.Queue()
        app.settings = {"endpoint": "https://example.com/chat", "model": "test-model"}
        app.ai_api_key = "test-key"
        app.history = []
        app.request_lock = threading.Lock()
        app.speech_stop_event = threading.Event()
        observed = []
        def finish_generation_with_stop(*_args, **_kwargs):
            # Simulate the user pressing STOP SPEECH while the AI is thinking.
            app.speech_stop_event.set()
            return "Namaste"
        def fake_speak(_text, stop_event):
            observed.append(stop_event.is_set())
            return False
        with (
            patch.object(jarvis_desktop, "chat_completion", side_effect=finish_generation_with_stop),
            patch.object(jarvis_desktop, "save_chat_history"),
            patch.object(jarvis_desktop, "speak_text_interruptibly", side_effect=fake_speak),
        ):
            app._answer_voice("hello JARVIS")
        self.assertEqual(observed, [True])


class ChatConfigurationTests(unittest.TestCase):
    def test_valid_configuration_is_trimmed(self):
        self.assertEqual(
            jarvis_desktop.validate_chat_configuration("  https://example.com/chat  ", " model-x "),
            ("https://example.com/chat", "model-x"),
        )

    def test_rejects_http_missing_host_credentials_and_invalid_port(self):
        for endpoint in (
            "http://example.com/chat",
            "https:///chat",
            "https://user:pass@example.com/chat",
            "https://example.com:99999/chat",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "valid HTTPS"):
                    jarvis_desktop.validate_chat_configuration(endpoint, "model")

    def test_rejects_blank_or_oversized_model(self):
        for model in (" ", "m" * 201):
            with self.subTest(model_length=len(model)):
                with self.assertRaisesRegex(ValueError, "model name"):
                    jarvis_desktop.validate_chat_configuration("https://example.com/chat", model)


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

    def test_requires_model_name(self):
        with self.assertRaisesRegex(ValueError, "model name"):
            jarvis_desktop.chat_completion(
                "https://example.com/v1/chat/completions",
                "",
                "test-key",
                "hello",
                [],
            )

    def test_requires_api_key(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            jarvis_desktop.chat_completion(
                "https://example.com/v1/chat/completions",
                "test-model",
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

    def test_history_with_unhashable_role_is_ignored(self):
        import json
        import tempfile
        path = Path(tempfile.mkdtemp()) / "history.json"
        path.write_text(json.dumps([{"role": ["user"], "content": "bad"}]), encoding="utf-8")
        self.assertEqual(jarvis_desktop.load_chat_history(path), [])

    def test_save_history_skips_unhashable_roles(self):
        import tempfile
        path = Path(tempfile.mkdtemp()) / "history.json"
        jarvis_desktop.save_chat_history([{"role": {"bad": "role"}, "content": "skip"}], path)
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


class SettingsPersistenceTests(unittest.TestCase):
    def test_settings_are_saved_atomically_and_reloaded(self):
        import tempfile
        path = Path(tempfile.mkdtemp()) / "settings.json"
        settings = {
            "endpoint": "https://example.com/chat",
            "model": "test-model",
            "language": "hi-IN",
            "start_with_windows": True,
        }
        jarvis_desktop.save_settings(settings, path)
        self.assertEqual(jarvis_desktop.load_settings(path), settings)
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_malformed_setting_types_fall_back_to_safe_defaults(self):
        import json
        import tempfile
        path = Path(tempfile.mkdtemp()) / "settings.json"
        path.write_text(json.dumps({
            "endpoint": ["not", "a", "string"],
            "model": None,
            "language": "unsupported",
            "start_with_windows": "yes",
        }), encoding="utf-8")
        loaded = jarvis_desktop.load_settings(path)
        self.assertEqual(loaded["endpoint"], jarvis_desktop.DEFAULT_ENDPOINT)
        self.assertEqual(loaded["model"], jarvis_desktop.DEFAULT_MODEL)
        self.assertEqual(loaded["language"], "en-IN")
        self.assertFalse(loaded["start_with_windows"])

    def test_non_string_language_does_not_crash_settings_loader(self):
        import json
        import tempfile
        path = Path(tempfile.mkdtemp()) / "settings.json"
        path.write_text(json.dumps({"language": ["hi-IN"]}), encoding="utf-8")
        loaded = jarvis_desktop.load_settings(path)
        self.assertEqual(loaded["language"], "en-IN")


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

    def test_hindi_full_stop_is_ignored_for_local_commands(self):
        calls = []
        result = jarvis_desktop.run_local_command(
            "नोटपैड खोलो।",
            popen=lambda args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertEqual(result, "Opening Notepad.")
        self.assertEqual(calls, [(["notepad.exe"], {"shell": False})])

    def test_hindi_double_danda_is_ignored_for_local_commands(self):
        from unittest.mock import patch
        with patch.object(jarvis_desktop, "press_windows_media_key", return_value=True) as press:
            result = jarvis_desktop.run_local_command("आवाज़ बढ़ाओ॥")
        self.assertEqual(result, "Volume increased.")
        press.assert_called_once_with("volume_up")

    def test_hindi_and_hinglish_app_aliases_use_the_same_safe_allowlist(self):
        calls = []
        for phrase in ("notepad kholo", "नोटपैड खोलो", "कैलकुलेटर खोलो"):
            jarvis_desktop.run_local_command(
                phrase, popen=lambda args, **kwargs: calls.append((args, kwargs)),
            )
        self.assertEqual([call[0] for call in calls], [
            ["notepad.exe"], ["notepad.exe"], ["calc.exe"],
        ])
        self.assertTrue(all(call[1] == {"shell": False} for call in calls))

    def test_hindi_and_hinglish_media_aliases_map_to_fixed_media_keys(self):
        from unittest.mock import patch
        with patch.object(jarvis_desktop, "press_windows_media_key", return_value=True) as press:
            self.assertEqual(jarvis_desktop.run_local_command("आवाज़ बढ़ाओ"), "Volume increased.")
            self.assertEqual(jarvis_desktop.run_local_command("volume kam karo"), "Volume decreased.")
        self.assertEqual([call.args[0] for call in press.call_args_list], ["volume_up", "volume_down"])

    def test_downloads_command_opens_fixed_user_folder_without_shell(self):
        calls = []
        result = jarvis_desktop.run_local_command(
            "open downloads",
            popen=lambda args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertEqual(result, "Opening Downloads.")
        self.assertEqual(
            calls,
            [(["explorer.exe", str(Path.home() / "Downloads")], {"shell": False})],
        )

    def test_downloads_folder_alias_opens_same_fixed_user_folder_without_shell(self):
        calls = []
        result = jarvis_desktop.run_local_command(
            "open downloads folder",
            popen=lambda args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertEqual(result, "Opening Downloads.")
        self.assertEqual(
            calls,
            [(["explorer.exe", str(Path.home() / "Downloads")], {"shell": False})],
        )

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
        details = {name: detail for name, _ready, detail in statuses}
        self.assertEqual(details["AI CHAT"], "CONFIGURED")
        self.assertEqual(details["VOICE ENGINE"], "CONFIGURED")


class SystemMetricsTests(unittest.TestCase):
    def test_battery_status_includes_charging_and_on_battery_state(self):
        from types import SimpleNamespace
        formatter = jarvis_desktop.JarvisDesktop._format_battery_status
        self.assertEqual(formatter(SimpleNamespace(percent=62, power_plugged=True)), "62% • CHARGING")
        self.assertEqual(formatter(SimpleNamespace(percent=62, power_plugged=False)), "62% • ON BATTERY")
        self.assertEqual(formatter(SimpleNamespace(percent=100, power_plugged=True)), "100%")
        self.assertEqual(formatter(None), "AC POWER")

    def test_invalid_battery_reading_is_reported_as_unavailable(self):
        from types import SimpleNamespace
        self.assertEqual(
            jarvis_desktop.JarvisDesktop._format_battery_status(
                SimpleNamespace(percent="unknown", power_plugged=False)
            ),
            "N/A",
        )

    def test_temperature_sensor_failure_does_not_hide_other_metrics(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        fake_psutil = SimpleNamespace(
            sensors_battery=lambda: SimpleNamespace(percent=80, power_plugged=True),
            disk_usage=lambda _drive: SimpleNamespace(percent=40),
            sensors_temperatures=lambda **_kwargs: (_ for _ in ()).throw(NotImplementedError()),
            net_if_stats=lambda: {"Ethernet": SimpleNamespace(isup=True)},
            cpu_percent=lambda interval=None: 12,
            virtual_memory=lambda: SimpleNamespace(percent=55),
        )
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            metrics = dict(app._get_system_metrics())
        self.assertEqual(metrics["CPU LOAD"], "12%")
        self.assertEqual(metrics["MEMORY"], "55%")
        self.assertEqual(metrics["DISK USED"], "40%")
        self.assertEqual(metrics["BATTERY"], "80% • CHARGING")
        self.assertEqual(metrics["CPU TEMP"], "N/A")
        self.assertEqual(metrics["NETWORK"], "ONLINE")


class WindowsBrightnessTests(unittest.TestCase):
    def test_brightness_increases_and_clamps_to_hundred(self):
        class FakeBrightness:
            def __init__(self):
                self.level = 95
                self.updated = None
            def get_brightness(self, display):
                self.asserted_display = display
                return [self.level]
            def set_brightness(self, level, display):
                self.updated = (level, display)
        fake = FakeBrightness()
        result = jarvis_desktop.adjust_windows_brightness(
            "up", brightness_module=fake, platform_name="nt",
        )
        self.assertEqual(result, 100)
        self.assertEqual(fake.updated, (100, 0))

    def test_brightness_decreases_and_clamps_to_zero(self):
        class FakeBrightness:
            def get_brightness(self, display):
                return [5]
            def set_brightness(self, level, display):
                self.updated = (level, display)
        fake = FakeBrightness()
        result = jarvis_desktop.adjust_windows_brightness(
            "down", brightness_module=fake, platform_name="nt",
        )
        self.assertEqual(result, 0)
        self.assertEqual(fake.updated, (0, 0))

    def test_brightness_rejects_unknown_direction_and_non_windows(self):
        with self.assertRaises(ValueError):
            jarvis_desktop.adjust_windows_brightness("sideways", platform_name="nt")
        with self.assertRaisesRegex(RuntimeError, "only on Windows"):
            jarvis_desktop.adjust_windows_brightness("up", platform_name="posix")

    def test_voice_brightness_commands_use_fixed_steps(self):
        from unittest.mock import patch
        with patch.object(jarvis_desktop, "adjust_windows_brightness", return_value=70) as adjust:
            self.assertEqual(
                jarvis_desktop.run_local_command("brightness up"),
                "Display brightness set to 70%.",
            )
            self.assertEqual(
                jarvis_desktop.run_local_command("decrease brightness"),
                "Display brightness set to 70%.",
            )
        self.assertEqual([call.args[0] for call in adjust.call_args_list], ["up", "down"])


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

    def test_explicit_unmute_and_pause_resume_are_not_misreported_as_toggles(self):
        from unittest.mock import patch
        with patch.object(jarvis_desktop, "press_windows_media_key") as press:
            self.assertIsNone(jarvis_desktop.run_local_command("unmute"))
            self.assertIsNone(jarvis_desktop.run_local_command("pause music"))
            self.assertIsNone(jarvis_desktop.run_local_command("resume music"))
        press.assert_not_called()


class WindowsStartupTests(unittest.TestCase):
    def test_development_startup_prefers_pythonw_and_quotes_paths_with_spaces(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "Python Runtime" / "python.exe"
            pythonw = python.with_name("pythonw.exe")
            pythonw.parent.mkdir(parents=True)
            pythonw.touch()
            script = root / "JARVIS Desktop" / "jarvis_desktop.py"
            command = jarvis_desktop.build_startup_command(
                executable=str(python), script_path=str(script), frozen=False,
            )
            self.assertEqual(
                command,
                f'"{pythonw}" "{script}"',
            )

    def test_development_startup_falls_back_to_python_when_pythonw_is_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            python = Path(directory) / "python.exe"
            command = jarvis_desktop.build_startup_command(
                executable=str(python), script_path="jarvis_desktop.py", frozen=False,
            )
            self.assertEqual(command, f'{python} jarvis_desktop.py')

    def test_startup_command_uses_frozen_executable(self):
        command = jarvis_desktop.build_startup_command(
            executable=r"C:\Program Files\JARVIS\JARVIS.exe", frozen=True,
        )
        self.assertEqual(command, '"C:\Program Files\JARVIS\JARVIS.exe"')

    def test_startup_registry_value_can_be_added_and_removed(self):
        class FakeRegistry:
            HKEY_CURRENT_USER = object()
            REG_SZ = 1
            def __init__(self):
                self.values = {}
                self.closed = False
            def CreateKey(self, root, path):
                self.asserted_path = path
                return "fake-key"
            def SetValueEx(self, key, name, reserved, kind, value):
                self.values[name] = (kind, value)
            def DeleteValue(self, key, name):
                if name not in self.values:
                    raise FileNotFoundError()
                del self.values[name]
            def CloseKey(self, key):
                self.closed = True

        registry = FakeRegistry()
        self.assertTrue(jarvis_desktop.set_windows_startup(
            True, winreg_module=registry,
            executable=r"C:\JARVIS\JARVIS.exe", frozen=True, platform_name="nt",
        ))
        self.assertEqual(registry.values["JARVIS"][1], r"C:\JARVIS\JARVIS.exe")
        self.assertTrue(registry.closed)
        self.assertEqual(registry.asserted_path, jarvis_desktop.STARTUP_RUN_KEY)
        self.assertTrue(jarvis_desktop.set_windows_startup(
            False, winreg_module=registry, platform_name="nt",
        ))
        self.assertNotIn("JARVIS", registry.values)

    def test_startup_registry_rejects_non_windows(self):
        with self.assertRaisesRegex(RuntimeError, "Windows"):
            jarvis_desktop.set_windows_startup(
                True, winreg_module=object(), platform_name="posix",
            )

    def test_startup_registry_key_is_closed_when_write_fails(self):
        class FailingRegistry:
            HKEY_CURRENT_USER = object()
            REG_SZ = 1
            closed = False
            def CreateKey(self, root, path):
                return "fake-key"
            def SetValueEx(self, *args):
                raise OSError("registry is unavailable")
            def CloseKey(self, key):
                self.closed = True

        registry = FailingRegistry()
        with self.assertRaisesRegex(OSError, "registry is unavailable"):
            jarvis_desktop.set_windows_startup(
                True, winreg_module=registry,
                executable=r"C:\\JARVIS\\JARVIS.exe", frozen=True,
                platform_name="nt",
            )
        self.assertTrue(registry.closed)

    def test_disabling_missing_startup_entry_is_safe_and_closes_key(self):
        class EmptyRegistry:
            HKEY_CURRENT_USER = object()
            closed = False
            def CreateKey(self, root, path):
                return "fake-key"
            def DeleteValue(self, key, name):
                raise FileNotFoundError()
            def CloseKey(self, key):
                self.closed = True

        registry = EmptyRegistry()
        self.assertTrue(jarvis_desktop.set_windows_startup(
            False, winreg_module=registry, platform_name="nt",
        ))
        self.assertTrue(registry.closed)


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


class ApplicationShutdownTests(unittest.TestCase):
    def test_exit_stops_listener_speech_and_tray_before_destroying_window(self):
        import threading

        class FakeRoot:
            def __init__(self):
                self.destroyed = False
            def destroy(self):
                self.destroyed = True

        class FakeTray:
            def __init__(self):
                self.stopped = False
            def stop(self):
                self.stopped = True

        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.stop_event = threading.Event()
        app.speech_stop_event = threading.Event()
        app.root = FakeRoot()
        app.tray_icon = FakeTray()
        tray = app.tray_icon

        app.exit_app()

        self.assertTrue(app.stop_event.is_set())
        self.assertTrue(app.speech_stop_event.is_set())
        self.assertTrue(tray.stopped)
        self.assertIsNone(app.tray_icon)
        self.assertTrue(app.root.destroyed)


class WakeRecorderCleanupTests(unittest.TestCase):
    def test_release_stops_active_recorder_before_deleting_it(self):
        calls = []

        class FakeRecorder:
            is_recording = True
            def stop(self):
                calls.append("stop")
            def delete(self):
                calls.append("delete")

        jarvis_desktop.release_wake_recorder(FakeRecorder())
        self.assertEqual(calls, ["stop", "delete"])

    def test_release_still_deletes_recorder_if_stop_fails(self):
        calls = []

        class FakeRecorder:
            is_recording = True
            def stop(self):
                calls.append("stop")
                raise OSError("device disconnected")
            def delete(self):
                calls.append("delete")

        jarvis_desktop.release_wake_recorder(FakeRecorder())
        self.assertEqual(calls, ["stop", "delete"])

    def test_release_handles_missing_recorder_and_delete_failure(self):
        class FakeRecorder:
            is_recording = False
            def delete(self):
                raise OSError("device already released")

        self.assertIsNone(jarvis_desktop.release_wake_recorder(None))
        self.assertIsNone(jarvis_desktop.release_wake_recorder(FakeRecorder()))


class VoiceRecognizerTimeoutTests(unittest.TestCase):
    def test_online_recognition_timeout_is_bounded(self):
        class FakeRecognizer:
            operation_timeout = None

        recognizer = jarvis_desktop.configure_voice_recognizer(FakeRecognizer())
        self.assertEqual(recognizer.operation_timeout, 8.0)

    def test_custom_positive_timeout_is_supported(self):
        class FakeRecognizer:
            operation_timeout = None

        recognizer = jarvis_desktop.configure_voice_recognizer(FakeRecognizer(), 3.5)
        self.assertEqual(recognizer.operation_timeout, 3.5)

    def test_non_positive_timeout_is_rejected(self):
        class FakeRecognizer:
            operation_timeout = None

        with self.assertRaises(ValueError):
            jarvis_desktop.configure_voice_recognizer(FakeRecognizer(), 0)


class CancellableVoiceCaptureTests(unittest.TestCase):
    def test_short_timeout_retries_until_a_command_is_received(self):
        import threading

        class WaitTimeoutError(Exception):
            pass

        class FakeRecognizer:
            def __init__(self):
                self.calls = 0
                self.recognized_language = None
            def listen(self, source, timeout, phrase_time_limit):
                self.calls += 1
                self.asserted_timeout = timeout
                self.asserted_phrase_limit = phrase_time_limit
                if self.calls == 1:
                    raise WaitTimeoutError()
                return "audio"
            def recognize_google(self, audio, language):
                self.recognized_language = language
                return "open downloads"

        recognizer = FakeRecognizer()
        command = jarvis_desktop.listen_for_voice_command(
            recognizer, object(), threading.Event(), "hi-IN", WaitTimeoutError,
        )
        self.assertEqual(command, "open downloads")
        self.assertEqual(recognizer.calls, 2)
        self.assertEqual(recognizer.asserted_timeout, 1)
        self.assertEqual(recognizer.asserted_phrase_limit, 12)
        self.assertEqual(recognizer.recognized_language, "hi-IN")

    def test_stop_during_idle_wait_does_not_start_cloud_recognition(self):
        import threading

        class WaitTimeoutError(Exception):
            pass

        stop_event = threading.Event()

        class FakeRecognizer:
            def listen(self, source, timeout, phrase_time_limit):
                stop_event.set()
                raise WaitTimeoutError()
            def recognize_google(self, audio, language):
                raise AssertionError("Recognition must not run after stop is requested.")

        command = jarvis_desktop.listen_for_voice_command(
            FakeRecognizer(), object(), stop_event, "en-IN", WaitTimeoutError,
        )
        self.assertIsNone(command)


    def test_preexisting_stop_does_not_open_or_read_microphone(self):
        import threading

        class WaitTimeoutError(Exception):
            pass

        stop_event = threading.Event()
        stop_event.set()

        class FakeRecognizer:
            def listen(self, source, timeout, phrase_time_limit):
                raise AssertionError("Microphone listen must not start after stop.")
            def recognize_google(self, audio, language):
                raise AssertionError("Cloud recognition must not start after stop.")

        command = jarvis_desktop.listen_for_voice_command(
            FakeRecognizer(), object(), stop_event, "en-IN", WaitTimeoutError,
        )
        self.assertIsNone(command)


class OfflineModelAutoSetupTests(unittest.TestCase):
    def test_missing_selected_model_is_downloaded_in_background(self):
        import queue
        from unittest.mock import patch
        from pathlib import Path

        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.settings = {"language": "hi-IN"}
        app.events = queue.Queue()
        app.offline_model_setup_running = False
        installed = Path("fake-model")

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon
            def start(self):
                self.target()

        with patch.object(jarvis_desktop, "model_path_for_language", return_value=Path("missing-model")), \
             patch.object(jarvis_desktop, "install_offline_model", return_value=installed) as install, \
             patch.object(jarvis_desktop.threading, "Thread", ImmediateThread):
            self.assertTrue(app._ensure_offline_model())

        install.assert_called_once_with("hi-IN")
        self.assertFalse(app.offline_model_setup_running)
        messages = []
        while not app.events.empty():
            messages.append(app.events.get_nowait())
        self.assertTrue(any("Offline voice is ready" in message for kind, message in messages))

    def test_existing_selected_model_is_not_downloaded_again(self):
        from pathlib import Path
        from unittest.mock import patch

        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.settings = {"language": "en-IN"}
        app.offline_model_setup_running = False
        with patch.object(jarvis_desktop, "model_path_for_language", return_value=Path("installed-model")) as model_path, \
             patch.object(jarvis_desktop, "install_offline_model") as install:
            model_path.return_value.is_dir = lambda: True
            self.assertFalse(app._ensure_offline_model())
        install.assert_not_called()


class OfflineVoiceFallbackTests(unittest.TestCase):
    def test_network_failure_uses_local_vosk_transcription(self):
        from unittest.mock import patch
        import threading

        class RequestError(Exception):
            pass
        class Recognizer:
            def listen(self, source, timeout, phrase_time_limit):
                return "captured-audio"
            def recognize_google(self, audio, language):
                raise RequestError("offline")
        with patch.object(jarvis_desktop, "transcribe_offline_vosk", return_value="notepad kholo") as offline:
            result = jarvis_desktop.listen_for_voice_command(
                Recognizer(), object(), threading.Event(), "hi-IN",
                TimeoutError, RequestError,
            )
        self.assertEqual(result, "notepad kholo")
        offline.assert_called_once_with("captured-audio", "hi-IN")

    def test_missing_offline_model_reports_setup_instructions(self):
        from unittest.mock import patch
        import threading

        class RequestError(Exception):
            pass
        class Recognizer:
            def listen(self, source, timeout, phrase_time_limit):
                return "captured-audio"
            def recognize_google(self, audio, language):
                raise RequestError("network unavailable")
        with patch.object(
            jarvis_desktop, "transcribe_offline_vosk",
            side_effect=jarvis_desktop.OfflineModelUnavailable("JARVIS will download it automatically when online."),
        ):
            with self.assertRaisesRegex(RequestError, "download it automatically"):
                jarvis_desktop.listen_for_voice_command(
                    Recognizer(), object(), threading.Event(), "en-IN",
                    TimeoutError, RequestError,
                )


if __name__ == "__main__":
    unittest.main()
