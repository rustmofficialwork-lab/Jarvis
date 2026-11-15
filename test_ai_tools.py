"""Tests for JARVIS's bounded, read-only AI tools."""
import unittest
from unittest.mock import patch

from ai_tools import calculate, execute_tool


class SafeToolTests(unittest.TestCase):
    def test_calculator_handles_basic_arithmetic(self):
        self.assertEqual(calculate("(12 + 8) * 3"), "60")
        self.assertEqual(calculate("7 / 2"), "3.5")
        self.assertEqual(calculate("2 ** 3"), "8")

    def test_calculator_rejects_code_and_names(self):
        for expression in ("__import__('os').system('whoami')", "open('x')", "x + 1"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    calculate(expression)

    def test_calculator_rejects_oversized_or_dangerous_math(self):
        for expression in ("9 ** 9", "1 / 0", "1e999 - 1e999", "9" * 121):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    calculate(expression)

    def test_tool_arguments_are_exact(self):
        self.assertEqual(execute_tool("calculator", {"expression": "6 * 7"}), "42")
        with self.assertRaises(ValueError):
            execute_tool("calculator", {"expression": "1+1", "extra": "ignored"})
        with self.assertRaises(ValueError):
            execute_tool("get_local_time", {"anything": True})
        with self.assertRaises(ValueError):
            execute_tool("get_system_status", {"anything": True})

    def test_system_status_tool_is_read_only_and_delegates_to_local_monitor(self):
        with patch("ai_tools.get_system_status", return_value="CPU usage: 12%") as status:
            self.assertEqual(execute_tool("get_system_status", {}), "CPU usage: 12%")
        status.assert_called_once_with()

    def test_top_processes_tool_uses_bounded_default_and_custom_limit(self):
        with patch("ai_tools.get_top_processes", return_value="Top processes") as processes:
            self.assertEqual(execute_tool("get_top_processes", {}), "Top processes")
            processes.assert_called_once_with(limit=5)
            self.assertEqual(execute_tool("get_top_processes", {"limit": 3}), "Top processes")
            processes.assert_called_with(limit=3)

    def test_top_processes_rejects_invalid_limits_and_extra_arguments(self):
        for arguments in ({"limit": 0}, {"limit": 11}, {"limit": True}, {"limit": "5"}, {"other": 1}):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    execute_tool("get_top_processes", arguments)

    def test_user_file_tools_list_search_and_read_only_safe_text(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            for folder in ("Desktop", "Documents", "Downloads"):
                (home / folder).mkdir()
            (home / "Documents" / "notes.txt").write_text("JARVIS project notes", encoding="utf-8")
            (home / "Documents" / "photo.png").write_bytes(b"not text")
            with patch("pathlib.Path.home", return_value=home):
                listed = execute_tool("list_user_files", {"folder": "Documents"})
                self.assertIn("notes.txt", listed)
                found = execute_tool("search_user_files", {"folder": "Documents", "query": "notes"})
                self.assertEqual(found, "notes.txt")
                self.assertEqual(execute_tool("read_user_text_file", {
                    "folder": "Documents", "filename": "notes.txt"
                }), "JARVIS project notes")
                with self.assertRaises(ValueError):
                    execute_tool("read_user_text_file", {
                        "folder": "Documents", "filename": "photo.png"
                    })

    def test_user_file_tools_reject_traversal_and_secret_files(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "Downloads").mkdir()
            (home / "secret.env").write_text("TOKEN=not-for-ai", encoding="utf-8")
            with patch("pathlib.Path.home", return_value=home):
                with self.assertRaises(ValueError):
                    execute_tool("read_user_text_file", {
                        "folder": "Downloads", "filename": "../secret.env"
                    })
                with self.assertRaises(ValueError):
                    execute_tool("read_user_text_file", {
                        "folder": "Downloads", "filename": "secret.env"
                    })

    def test_open_website_allows_public_https_url_and_reports_navigation_only(self):
        with patch("ai_tools.webbrowser.open", return_value=True) as open_browser:
            result = execute_tool("open_website", {"url": "https://example.com/path?q=jarvis#section"})
        self.assertIn("has not signed in", result)
        open_browser.assert_called_once_with(
            "https://example.com/path?q=jarvis", new=2, autoraise=True
        )

    def test_open_website_blocks_local_private_and_credential_urls(self):
        blocked = (
            "file:///C:/Windows/win.ini",
            "javascript:alert(1)",
            "http://localhost/admin",
            "http://127.0.0.1/",
            "http://192.168.1.1/",
            "https://user:pass@example.com/",
            "https://example.com:8443/",
        )
        with patch("ai_tools.webbrowser.open") as open_browser:
            for url in blocked:
                with self.subTest(url=url):
                    with self.assertRaises(ValueError):
                        execute_tool("open_website", {"url": url})
            open_browser.assert_not_called()

    def test_open_app_uses_only_fixed_windows_command_without_shell(self):
        import sys
        with patch("ai_tools.sys.platform", "win32"), patch("ai_tools.subprocess.Popen") as popen:
            result = execute_tool("open_app", {"app": "notepad"})
        self.assertIn("Launch request sent", result)
        popen.assert_called_once_with(["notepad.exe"], shell=False, close_fds=True)

    def test_open_app_rejects_arbitrary_commands_and_non_windows(self):
        with patch("ai_tools.sys.platform", "linux"):
            with self.assertRaises(ValueError):
                execute_tool("open_app", {"app": "notepad"})
        with patch("ai_tools.sys.platform", "win32", create=True):
            with self.assertRaises(ValueError):
                execute_tool("open_app", {"app": "powershell"})
            with self.assertRaises(ValueError):
                execute_tool("open_app", {"app": "notepad", "command": "whoami"})

    def test_capabilities_tool_reports_implemented_and_unsupported_actions(self):
        result = execute_tool("get_available_capabilities", {})
        self.assertIn("web search, weather, and news", result)
        self.assertIn("payments", result)
        self.assertIn("arbitrary browser automation", result)

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            execute_tool("run_shell", {})

    def test_local_time_is_timezone_aware(self):
        value = execute_tool("get_local_time", {})
        self.assertRegex(value, r".+[+-]\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
