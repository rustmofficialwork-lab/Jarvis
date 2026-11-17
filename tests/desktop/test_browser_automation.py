import threading
import unittest
from unittest.mock import Mock, patch

from browser_automation import BrowserAutomation, BrowserAutomationError


class BrowserAutomationTests(unittest.TestCase):
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
        browser._context = object()
        return browser, locator

    def test_sensitive_click_requires_exact_approval(self):
        browser, locator = self._fake_browser("Send message")
        with self.assertRaises(PermissionError):
            browser.act("click", selector="button.send")
        locator.click.assert_not_called()

        approved = []
        result = browser.act(
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
            browser.act("click", selector="button.buy",
                        approval_callback=lambda *_: True)
        locator.click.assert_not_called()

    def test_ambiguous_selectors_are_rejected(self):
        browser, locator = self._fake_browser("Search")
        locator.count.return_value = 2
        with self.assertRaises(BrowserAutomationError):
            browser.act("click", selector="button")


if __name__ == "__main__":
    unittest.main()
