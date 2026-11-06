from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.main import (
    DEVICE_TOKEN_TTL_SECONDS,
    _issue_device_token,
    _verify_device_token,
)


class DeviceTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "test-only-signing-secret-that-is-at-least-32-bytes"

    def test_issued_token_round_trips_for_installation(self) -> None:
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": self.secret}):
            token, expires_at = _issue_device_token(
                "8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa", now=1_800_000_000
            )
            self.assertEqual(
                _verify_device_token(token, now=1_800_000_001),
                "8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa",
            )
            self.assertEqual(expires_at, 1_800_000_000 + DEVICE_TOKEN_TTL_SECONDS)

    def test_expired_token_is_rejected(self) -> None:
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": self.secret}):
            token, expires_at = _issue_device_token(
                "8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa", now=1_800_000_000
            )
            self.assertIsNone(_verify_device_token(token, now=expires_at))

    def test_tampered_token_is_rejected(self) -> None:
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": self.secret}):
            token, _ = _issue_device_token(
                "8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa", now=1_800_000_000
            )
            replacement = "A" if token[-1] != "A" else "B"
            self.assertIsNone(_verify_device_token(token[:-1] + replacement, now=1_800_000_001))

    def test_token_from_another_secret_is_rejected(self) -> None:
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": self.secret}):
            token, _ = _issue_device_token(
                "8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa", now=1_800_000_000
            )
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": "a-different-signing-secret-at-least-32-bytes"}):
            self.assertIsNone(_verify_device_token(token, now=1_800_000_001))

    def test_missing_signing_secret_does_not_issue_tokens(self) -> None:
        with patch.dict(os.environ, {"JARVIS_DEVICE_TOKEN_SECRET": ""}):
            with self.assertRaises(Exception):
                _issue_device_token("8d0a7c32-bc9e-4a4d-9f01-2f0db7e2e3aa", now=1_800_000_000)


if __name__ == "__main__":
    unittest.main()
