import unittest

from brain_core import authorize_tool_call, choose_mode


class BrainCoreTests(unittest.TestCase):
    def test_auto_mode_selects_hybrid_when_both_routes_exist(self):
        self.assertEqual(
            choose_mode("auto", internet_available=True, local_model_available=True),
            "hybrid",
        )

    def test_auto_mode_falls_back_to_offline(self):
        self.assertEqual(
            choose_mode("auto", internet_available=False, local_model_available=True),
            "offline",
        )

    def test_forced_online_does_not_silently_use_offline(self):
        self.assertEqual(
            choose_mode("online", internet_available=False, local_model_available=True),
            "unavailable",
        )

    def test_read_only_tools_are_allowed(self):
        decision = authorize_tool_call("get_system_status", {}, "How is my PC?")
        self.assertTrue(decision.allowed)

    def test_open_app_requires_direct_request_and_named_app(self):
        denied = authorize_tool_call("open_app", {"app": "notepad"}, "What is Notepad?")
        allowed = authorize_tool_call("open_app", {"app": "notepad"}, "Please open Notepad")
        wrong_app = authorize_tool_call("open_app", {"app": "paint"}, "Please open Notepad")
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)
        self.assertFalse(wrong_app.allowed)
        negated = authorize_tool_call("open_app", {"app": "notepad"}, "Do not open Notepad")
        question = authorize_tool_call("open_app", {"app": "notepad"}, "How do I open Notepad?")
        self.assertFalse(negated.allowed)
        self.assertFalse(question.allowed)

    def test_website_navigation_requires_the_named_site_and_direct_intent(self):
        allowed = authorize_tool_call(
            "open_website", {"url": "https://www.youtube.com"}, "Please open YouTube"
        )
        denied = authorize_tool_call(
            "open_website", {"url": "https://attacker.example"}, "Please open YouTube"
        )
        informational = authorize_tool_call(
            "open_website", {"url": "https://www.youtube.com"}, "How do I open YouTube?"
        )
        deceptive_suffix = authorize_tool_call(
            "open_website", {"url": "https://youtube.com.attacker.invalid"}, "Please open YouTube"
        )
        valid_subdomain = authorize_tool_call(
            "open_website", {"url": "https://music.youtube.com"}, "Please open YouTube"
        )
        self.assertTrue(allowed.allowed)
        self.assertFalse(denied.allowed)
        self.assertFalse(informational.allowed)
        self.assertFalse(deceptive_suffix.allowed)
        self.assertTrue(valid_subdomain.allowed)

    def test_sensitive_actions_never_run_from_model_tool_call(self):
        decision = authorize_tool_call("send_money", {"amount": 100}, "Send 100")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, "confirmation_required")

    def test_unknown_tools_are_denied(self):
        decision = authorize_tool_call("run_shell_command", {"command": "whoami"}, "Run it")
        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
