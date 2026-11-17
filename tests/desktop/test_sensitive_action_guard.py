import unittest

from sensitive_action_guard import (
    ApprovalLedger, BrowserSessionPolicy, build_approval_request,
)


class SensitiveActionGuardTests(unittest.TestCase):
    def test_approval_is_bound_to_exact_details_and_consumed_once(self):
        clock = [100.0]
        ledger = ApprovalLedger(clock=lambda: clock[0])
        details = {"recipient": "person@example.test", "subject": "Hello", "content": "Final text"}
        request = build_approval_request("email", details, "Send email", now=100.0)
        token = ledger.request(request)
        self.assertTrue(ledger.decide(token, approved=True).approved)
        changed = dict(details, content="Changed after approval")
        self.assertFalse(ledger.consume("email", changed).approved)
        self.assertTrue(ledger.consume("email", details).approved)
        self.assertFalse(ledger.consume("email", details).approved)


    def test_preview_details_are_returned_as_immutable_copies(self):
        details = {"recipient": "person@example.test", "subject": "Hi", "content": "Final"}
        request = build_approval_request("email", details, "Send email")
        exposed = request.details
        exposed["content"] = "Tampered"
        self.assertEqual(request.details["content"], "Final")

    def test_expired_pending_requests_are_purged_before_capacity_check(self):
        clock = [100.0]
        ledger = ApprovalLedger(clock=lambda: clock[0])
        request = build_approval_request(
            "message", {"recipient": "contact", "content": "Hi"}, "Send message", now=100.0
        )
        for _ in range(32):
            ledger.request(request)
        clock[0] = 221.0
        # Expired pending entries are discarded, so they cannot permanently fill the queue.
        self.assertTrue(ledger.request(build_approval_request(
            "message", {"recipient": "other", "content": "Hello"}, "Send message", now=221.0
        )))

    def test_expired_approved_grant_is_purged_and_cannot_be_consumed(self):
        clock = [100.0]
        ledger = ApprovalLedger(clock=lambda: clock[0])
        details = {"recipient": "contact", "content": "Hi"}
        token = ledger.request(build_approval_request("message", details, "Send message", now=100.0))
        self.assertTrue(ledger.decide(token, approved=True).approved)
        clock[0] = 221.0
        self.assertEqual(ledger.consume("message", details).status, "approval_required")

    def test_already_expired_request_cannot_be_queued(self):
        clock = [221.0]
        ledger = ApprovalLedger(clock=lambda: clock[0])
        request = build_approval_request(
            "message", {"recipient": "contact", "content": "Hi"}, "Send message", now=100.0
        )
        with self.assertRaises(ValueError):
            ledger.request(request)

    def test_denial_and_expiry_never_grant(self):
        clock = [100.0]
        ledger = ApprovalLedger(clock=lambda: clock[0])
        request = build_approval_request(
            "message", {"recipient": "contact", "content": "Hi"}, "Send message", now=100.0
        )
        token = ledger.request(request)
        self.assertEqual(ledger.decide(token, approved=False).status, "denied")
        token = ledger.request(request)
        clock[0] = 221.0
        self.assertEqual(ledger.decide(token, approved=True).status, "expired")

    def test_payment_preview_requires_amount_recipient_and_purpose(self):
        with self.assertRaises(ValueError):
            build_approval_request("payment", {"amount": 50}, "Payment")
        request = build_approval_request(
            "payment",
            {"amount": 50, "currency": "INR", "recipient": "Example", "purpose": "Test"},
            "Payment preview",
        )
        self.assertEqual(request.action_type, "payment")

    def test_payment_and_purchase_reject_non_finite_amounts(self):
        for amount in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(action="payment", amount=amount), self.assertRaises(ValueError):
                build_approval_request(
                    "payment",
                    {"amount": amount, "currency": "INR", "recipient": "Example", "purpose": "Test"},
                    "Payment preview",
                )
            with self.subTest(action="purchase", amount=amount), self.assertRaises(ValueError):
                build_approval_request(
                    "purchase",
                    {"product": "Item", "price": amount, "currency": "INR", "order": "1 item"},
                    "Purchase preview",
                )

    def test_purchase_preview_requires_product_price_and_order(self):
        with self.assertRaises(ValueError):
            build_approval_request("purchase", {"product": "Item"}, "Purchase")
        request = build_approval_request(
            "purchase",
            {"product": "Item", "price": 99, "currency": "INR", "order": "1 item"},
            "Purchase preview",
        )
        self.assertEqual(request.action_type, "purchase")

    def test_delete_requires_exact_paths_and_recovery(self):
        with self.assertRaises(ValueError):
            build_approval_request(
                "delete", {"paths": ["C:/temp/a.txt"], "recovery": False}, "Delete"
            )
        request = build_approval_request(
            "delete", {"paths": ["C:/temp/a.txt"], "recovery": True}, "Move to recycle bin"
        )
        self.assertEqual(request.details["paths"], ["C:/temp/a.txt"])

    def test_browser_policy_is_exact_domain_and_bounded(self):
        policy = BrowserSessionPolicy(["example.com"])
        self.assertTrue(policy.authorize("example.com", "open_page").approved)
        self.assertEqual(policy.authorize("sub.example.com", "open_page").status, "domain_denied")
        for malformed in ("https://example.com", "example.com/path", "example.com:443"):
            self.assertEqual(policy.authorize(malformed, "open_page").status, "domain_denied")
        self.assertEqual(policy.authorize("example.com", "checkout").status, "action_denied")
        self.assertEqual(policy.authorize("example.com", "send_email").status, "action_denied")
        self.assertEqual(policy.authorize("example.com", "submit_form").status, "action_denied")
        self.assertEqual(policy.authorize("example.com", "run_shell_command").status, "action_denied")
        self.assertEqual(policy.authorize("example.com", "click_link").status, "action_denied")
        self.assertTrue(policy.authorize("example.com", "extract_text").approved)
        for _ in range(18):
            self.assertTrue(policy.authorize("example.com", "read_page").approved)
        self.assertEqual(policy.authorize("example.com", "read_page").status, "limit_reached")

    def test_browser_action_limit_is_thread_safe(self):
        from concurrent.futures import ThreadPoolExecutor
        policy = BrowserSessionPolicy(["example.com"])
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(
                lambda _index: policy.authorize("example.com", "read_page"),
                range(100),
            ))
        self.assertEqual(sum(result.approved for result in results), 20)
        self.assertEqual(sum(result.status == "limit_reached" for result in results), 80)
        self.assertEqual(policy.actions_used, 20)

    def test_browser_policy_rejects_wildcards_and_urls(self):
        for domain in ("*.example.com", "https://example.com/path", "example.com/path"):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                BrowserSessionPolicy([domain])

    def test_browser_policy_rejects_ip_literals_and_malformed_dns_names(self):
        invalid_domains = (
            "127.0.0.1", "::1", "[::1]", "example..com",
            "-example.com", "example-.com", "example.com:443",
            "example.com\\n.evil", "example .com", "example.com.",
        )
        for domain in invalid_domains:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                BrowserSessionPolicy([domain])

    def test_browser_authorization_rejects_malformed_hostname_inputs(self):
        policy = BrowserSessionPolicy(["example.com"])
        for domain in ("127.0.0.1", "example..com", "https://example.com", "example.com:443"):
            with self.subTest(domain=domain):
                self.assertEqual(
                    policy.authorize(domain, "read_page").status,
                    "domain_denied",
                )

    def test_browser_approval_preview_requires_valid_dns_hostname(self):
        for domain in ("127.0.0.1", "example..com", "*.example.com", "https://example.com"):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                build_approval_request(
                    "browser", {"domain": domain, "action": "read_page"}, "Read public page"
                )

    def test_browser_approval_preview_fails_closed_on_unlisted_actions(self):
        for action in ("click_link", "submit_form", "run_shell_command", "unknown"):
            with self.subTest(action=action), self.assertRaises(PermissionError):
                build_approval_request(
                    "browser",
                    {"domain": "example.com", "action": action},
                    "Browser action",
                )

    def test_browser_approval_preview_accepts_only_read_only_allowlist(self):
        for action in ("open_page", "read_page", "extract_text", "scroll_page"):
            with self.subTest(action=action):
                request = build_approval_request(
                    "browser",
                    {"domain": "example.com", "action": action},
                    "Read public page",
                )
                self.assertEqual(request.details["action"], action)


if __name__ == "__main__":
    unittest.main()
