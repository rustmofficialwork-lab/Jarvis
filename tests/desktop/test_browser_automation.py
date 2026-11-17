import threading
import unittest
from unittest.mock import Mock, patch

from browser_automation import BrowserAutomation, BrowserAutomationError


class BrowserAutomationTests(unittest.TestCase):
    def test_browser_commands_are_serialized_on_a_dedicated_worker(self):
        import tempfile
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as directory:
            browser = BrowserAutomation(directory)
            with ThreadPoolExecutor(max_workers=4) as pool:
                statuses = list(pool.map(lambda _index: browser.status(), range(8)))
            self.assertTrue(all(status["running"] is False for status in statuses))
            browser.close()
            self.assertFalse(browser._worker.is_alive())

    def test_url_validation_requires_public_https_and_blocks_private_dns(self):
        public = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("browser_automation.socket.getaddrinfo", return_value=public):
            host, url = BrowserAutomation._validate_url("https://example.com/path")
        self.assertEqual(host, "example.com")
        self.assertEqual(url, "https://example.com/path")

        with self.assertRaises(ValueError):
            BrowserAutomation._validate_url("http://example.com")
        with self.assertRaises(ValueError):
            BrowserAutomation._validate_url("https://127.0.0.1")

        private = [(2, 1, 6, "", ("192.168.1.20", 443))]
        with patch("browser_automation.socket.getaddrinfo", return_value=private):
            with self.assertRaises(ValueError):
                BrowserAutomation._validate_url("https://private.example")

    def _fake_browser(self, label):
        browser = object.__new__(BrowserAutomation)
        browser._lock = threading.RLock()
        browser._steps = 0
        browser._host = "example.com"
        locator = Mock()
        locator.count.return_value = 1
        locator.first = locator
        locator.is_visible.return_value = True
        locator.inner_text.return_value = label
        locator.get_attribute.return_value = None
        page = Mock()
        page.is_closed.return_value = False
        page.url = "https://example.com/"
        page.locator.return_value = locator
        browser._page = page
        browser._page_hosts = {id(page): "example.com"}
        browser._context = object()
        return browser, locator

    def test_sensitive_click_requires_exact_approval(self):
        browser, locator = self._fake_browser("Send message")
        with self.assertRaises(PermissionError):
            browser._act_local("click", selector="button.send")
        locator.click.assert_not_called()

        approved = []
        result = browser._act_local(
            "click", selector="button.send",
            approval_callback=lambda details, summary: approved.append((details, summary)) or True,
        )
        self.assertIn("Clicked", result)
        self.assertEqual(approved[0][0]["domain"], "example.com")
        self.assertEqual(approved[0][0]["action"], "click_sensitive_control")
        locator.click.assert_called_once()

    def test_checkout_controls_are_blocked_even_if_approval_callback_exists(self):
        browser, locator = self._fake_browser("Buy now")
        with self.assertRaises(PermissionError):
            browser._act_local("click", selector="button.buy",
                        approval_callback=lambda *_: True)
        locator.click.assert_not_called()

    def test_ambiguous_selectors_are_rejected(self):
        browser, locator = self._fake_browser("Search")
        locator.count.return_value = 2
        with self.assertRaises(BrowserAutomationError):
            browser._act_local("click", selector="button")

    def test_search_submission_needs_no_voice_approval(self):
        browser, locator = self._fake_browser("Search")
        result = browser._act_local(
            "press", selector="form.search", value="Enter"
        )
        self.assertIn("ordinary search form", result)
        locator.press.assert_called_once_with("Enter")

    def test_sensitive_form_submission_requires_approval(self):
        browser, locator = self._fake_browser("Contact form")
        with self.assertRaises(PermissionError):
            browser._act_local("press", selector="form.contact", value="Enter")
        locator.press.assert_not_called()

        approved = []
        result = browser._act_local(
            "press", selector="form.contact", value="Enter",
            approval_callback=lambda details, summary: approved.append(details) or True,
        )
        self.assertIn("exact one-time voice approval", result)
        self.assertEqual(approved[0], {
            "domain": "example.com", "action": "submit_form",
            "selector": "form.contact", "key": "Enter",
        })
        locator.press.assert_called_once_with("Enter")

    def test_secret_fields_are_blocked_and_ordinary_fields_remain_fillable(self):
        sensitive_names = (
            "password", "passcode", "pin", "otp", "one_time_code",
            "api_token", "client_secret", "cvv", "cvc", "card_number",
        )
        for field_name in sensitive_names:
            with self.subTest(field_name=field_name):
                browser, locator = self._fake_browser("Search")
                locator.get_attribute.side_effect = (
                    lambda attribute, name=field_name: (
                        "text" if attribute == "type"
                        else name if attribute == "name"
                        else None
                    )
                )
                with self.assertRaises(PermissionError):
                    browser._act_local(
                        "fill", selector="input", value="must-not-be-entered"
                    )
                locator.fill.assert_not_called()

        browser, locator = self._fake_browser("Search")
        locator.get_attribute.side_effect = (
            lambda attribute: (
                "text" if attribute == "type"
                else "search_query" if attribute == "name"
                else None
            )
        )
        result = browser._act_local(
            "fill", selector="input.search", value="weather today"
        )
        self.assertIn("Filled", result)
        locator.fill.assert_called_once_with("weather today")


if __name__ == "__main__":
    unittest.main()
