import hashlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from updater import API_URL, INSTALLER_NAME, check_for_update, download_verified_installer


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        return FakeResponse(self.responses.pop(0))


class UpdaterTests(unittest.TestCase):
    def test_no_release_yet(self):
        class NotFound:
            def __call__(self, request, timeout):
                import urllib.error
                raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)
        result = check_for_update("1.0.0", NotFound())
        self.assertFalse(result["available"])
        self.assertFalse(result["release_exists"])

    def test_check_finds_newer_release_and_expected_assets(self):
        payload = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/tag/v1.2.0",
            "assets": [
                {"name": INSTALLER_NAME, "browser_download_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/v1.2.0/" + INSTALLER_NAME, "digest": "sha256:" + "a" * 64},
            ],
        }
        result = check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "1.2.0")

    def test_newer_release_requires_valid_asset_digest(self):
        payload = {
            "tag_name": "v1.2.0",
            "assets": [
                {"name": INSTALLER_NAME, "browser_download_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/v1.2.0/" + INSTALLER_NAME},
            ],
        }
        with self.assertRaisesRegex(RuntimeError, "digest is missing or invalid"):
            check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))

    def test_rolling_latest_tag_uses_numeric_version_from_release_body(self):
        payload = {
            "tag_name": "jarvis-latest",
            "body": "Latest successful Windows desktop build.\nVersion: 1.1.345\n",
            "assets": [
                {"name": INSTALLER_NAME, "browser_download_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/jarvis-latest/" + INSTALLER_NAME, "digest": "sha256:" + "b" * 64},
            ],
        }
        result = check_for_update("1.1.344", FakeOpener([json.dumps(payload).encode()]))
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "1.1.345")
        self.assertEqual(result["tag"], "jarvis-latest")

    def test_rolling_latest_tag_rejects_missing_version_metadata(self):
        payload = {"tag_name": "jarvis-latest", "body": "Latest build", "assets": []}
        with self.assertRaisesRegex(RuntimeError, "missing numeric version metadata"):
            check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))

    def test_current_version_is_not_offered_again(self):
        payload = {"tag_name": "v1.1.0", "assets": []}
        result = check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))
        self.assertFalse(result["available"])

    def test_rejects_unsafe_asset_url(self):
        payload = {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": INSTALLER_NAME, "browser_download_url": "https://example.com/setup.exe", "digest": "sha256:" + "c" * 64},
            ],
        }
        with self.assertRaisesRegex(ValueError, "unsafe"):
            check_for_update("1.0.0", FakeOpener([json.dumps(payload).encode()]))

    def test_download_verifies_hash_before_writing(self):
        installer = b"sample installer bytes"
        digest = hashlib.sha256(installer).hexdigest()
        opener = FakeOpener([installer])
        with tempfile.TemporaryDirectory() as folder:
            path = download_verified_installer(
                "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                digest,
                folder, opener,
            )
            self.assertEqual(path.read_bytes(), installer)

    def test_rejects_tampered_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                download_verified_installer(
                    "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                    "0" * 64,
                    folder, FakeOpener([b"tampered"]),
                )
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_streaming_download_enforces_size_limit_and_cleans_partial_file(self):
        import updater
        installer = b"12345"
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(updater, "MAX_INSTALLER_BYTES", 4):
                with self.assertRaisesRegex(ValueError, "200 MB safety limit"):
                    download_verified_installer(
                        "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                        hashlib.sha256(installer).hexdigest(),
                        folder, FakeOpener([installer]),
                    )
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_failed_verification_preserves_previous_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            existing = Path(folder) / INSTALLER_NAME
            existing.write_bytes(b"known-good installer")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                download_verified_installer(
                    "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                    "0" * 64,
                    folder, FakeOpener([b"tampered"]),
                )
            self.assertEqual(existing.read_bytes(), b"known-good installer")
            self.assertEqual([p.name for p in Path(folder).iterdir()], [INSTALLER_NAME])

    def test_redirect_allowlist_rejects_unapproved_hosts_and_nonstandard_ports(self):
        from updater import _is_allowed_redirect_url

        self.assertTrue(_is_allowed_redirect_url("https://objects.githubusercontent.com/assets/file"))
        self.assertTrue(_is_allowed_redirect_url("https://release-assets.githubusercontent.com/file"))
        self.assertFalse(_is_allowed_redirect_url("http://objects.githubusercontent.com/file"))
        self.assertFalse(_is_allowed_redirect_url("https://example.com/file"))
        self.assertFalse(_is_allowed_redirect_url("https://github.com:444/file"))
        self.assertFalse(_is_allowed_redirect_url("https://user@github.com/file"))
        self.assertFalse(_is_allowed_redirect_url("https://github.com:bad/file"))

    def test_rejects_non_github_download_url(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                download_verified_installer(
                    "https://example.com/" + INSTALLER_NAME,
                    "0" * 64,
                    folder,
                )


if __name__ == "__main__":
    unittest.main()
