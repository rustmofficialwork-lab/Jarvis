"""Tests for the approval-gated external provider adapters."""
import os
import unittest
from unittest.mock import patch

from provider_integrations import (
    IntegrationUnavailable,
    integration_status,
    read_browser_page,
    send_gmail_email,
    send_outlook_email,
    send_telegram_message,
    send_whatsapp_message,
    run_approved_action,
)


class Approved:
    approved = True


class ProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.approved_details = []
        self.consume = lambda details: self._approve(details)

    def _approve(self, details):
        self.approved_details.append(details)
        return Approved()

    def test_gmail_requires_exact_approval_before_provider_call(self):
        with patch.dict(os.environ, {
            "JARVIS_GMAIL_ACCESS_TOKEN": "test-token",
            "JARVIS_GMAIL_USER": "owner@example.com",
        }), patch("provider_integrations._request_json", return_value={}) as request:
            result = send_gmail_email(
                "person@example.com", "Hello", "Final body", consume_approval=self.consume
            )
        self.assertIn("person@example.com", result)
        self.assertEqual(self.approved_details, [{
            "recipient": "person@example.com", "subject": "Hello", "content": "Final body"
        }])
        request.assert_called_once()
        self.assertIn("raw", request.call_args.kwargs["payload"])

    def test_outlook_uses_graph_sendmail_payload(self):
        with patch.dict(os.environ, {"JARVIS_GRAPH_ACCESS_TOKEN": "test-token"}), \
             patch("provider_integrations._request_json", return_value={}) as request:
            send_outlook_email("person@example.com", "Subject", "Body", consume_approval=self.consume)
        self.assertEqual(request.call_args.kwargs["payload"]["message"]["toRecipients"][0]["emailAddress"]["address"],
                         "person@example.com")
        self.assertEqual(request.call_args.kwargs["payload"]["message"]["body"]["content"], "Body")

    def test_telegram_requires_numeric_chat_id_and_approval(self):
        with patch.dict(os.environ, {"JARVIS_TELEGRAM_BOT_TOKEN": "test-token"}), \
             patch("provider_integrations._request_json", return_value={"ok": True}) as request:
            result = send_telegram_message("123456", "Hello", consume_approval=self.consume)
        self.assertIn("123456", result)
        self.assertEqual(request.call_args.kwargs["payload"], {"chat_id": "123456", "text": "Hello"})
        with self.assertRaises(ValueError):
            send_telegram_message("someone", "Hello", consume_approval=self.consume)

    def test_denied_approval_never_contacts_provider(self):
        with patch.dict(os.environ, {"JARVIS_GRAPH_ACCESS_TOKEN": "test-token"}), \
             patch("provider_integrations._request_json") as request:
            with self.assertRaises(PermissionError):
                send_outlook_email("person@example.com", "Subject", "Body",
                                   consume_approval=lambda details: type("Denied", (), {"approved": False})())
        request.assert_not_called()

    def test_missing_credentials_are_reported_without_secret_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(IntegrationUnavailable):
                send_gmail_email("person@example.com", "Subject", "Body",
                                 consume_approval=self.consume)
            status = integration_status()
        self.assertEqual(status["gmail"], "needs_local_oauth_setup")
        self.assertNotIn("TOKEN", repr(status))

    def test_whatsapp_uses_official_cloud_api_and_exact_approval(self):
        env = {
            "JARVIS_WHATSAPP_ACCESS_TOKEN": "test-token",
            "JARVIS_WHATSAPP_PHONE_NUMBER_ID": "123456",
        }
        with patch.dict(os.environ, env), \\
             patch("provider_integrations._request_json", return_value={"messages": [{"id": "wamid.test"}]}) as request:
            result = send_whatsapp_message("+14155550123", "Hello", consume_approval=self.consume)
        self.assertIn("+14155550123", result)
        self.assertEqual(request.call_args.kwargs["payload"]["to"], "+14155550123")

    def test_native_approval_bridge_requests_and_consumes_same_details(self):
        class Brain:
            def __init__(self):
                self.consumed = []
            def consume_sensitive_approval(self, action_type, details):
                self.consumed.append((action_type, details))
                return Approved()

        class App:
            def __init__(self):
                self.brain_engine = Brain()
                self.requested = []
            def request_sensitive_action_approval(self, action_type, details, summary):
                self.requested.append((action_type, details, summary))
                return True

        app = App()
        details = {"recipient": "person@example.com", "subject": "Hi", "content": "Exact"}
        result = run_approved_action(
            app, "email", details, "Send exact email",
            lambda consume: ("sent" if consume(details).approved else "blocked"),
        )
        self.assertEqual(result, "sent")
        self.assertEqual(app.requested[0][:2], ("email", details))
        self.assertEqual(app.brain_engine.consumed, [("email", details)])

    def test_native_approval_bridge_stops_when_user_denies(self):
        class App:
            brain_engine = object()
            def request_sensitive_action_approval(self, *args):
                return False
        called = []
        with self.assertRaises(PermissionError):
            run_approved_action(App(), "message", {"recipient": "123", "content": "Hi"},
                                "Send message", lambda consume: called.append(True))
        self.assertEqual(called, [])

    def test_browser_requires_https_exact_allowlist_and_approval(self):
        with self.assertRaises(PermissionError):
            read_browser_page("https://example.com", allowed_domains=["other.example"],
                              consume_approval=self.consume)
        with self.assertRaises(ValueError):
            read_browser_page("http://example.com", allowed_domains=["example.com"],
                              consume_approval=self.consume)
        self.assertEqual(self.approved_details, [])

    def test_browser_requires_approval_before_optional_dependency(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(IntegrationUnavailable):
                read_browser_page("https://example.com", allowed_domains=["example.com"],
                                  consume_approval=self.consume)
        self.assertEqual(self.approved_details, [{"domain": "example.com", "action": "read_page"}])


if __name__ == "__main__":
    unittest.main()
