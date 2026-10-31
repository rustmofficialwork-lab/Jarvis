import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from updater import API_URL, CHECKSUM_NAME, INSTALLER_NAME, check_for_update, download_verified_installer


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
                {"name": INSTALLER_NAME, "browser_download_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/v1.2.0/" + INSTALLER_NAME},
                {"name": CHECKSUM_NAME, "browser_download_url": "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/v1.2.0/" + CHECKSUM_NAME},
            ],
        }
        result = check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "1.2.0")

    def test_current_version_is_not_offered_again(self):
        payload = {"tag_name": "v1.1.0", "assets": []}
        result = check_for_update("1.1.0", FakeOpener([json.dumps(payload).encode()]))
        self.assertFalse(result["available"])

    def test_rejects_unsafe_asset_url(self):
        payload = {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": INSTALLER_NAME, "browser_download_url": "https://example.com/setup.exe"},
                {"name": CHECKSUM_NAME, "browser_download_url": "https://github.com/org/repo/checksums"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "unsafe"):
            check_for_update("1.0.0", FakeOpener([json.dumps(payload).encode()]))

    def test_download_verifies_hash_before_writing(self):
        installer = b"sample installer bytes"
        digest = hashlib.sha256(installer).hexdigest()
        checksum = f"{digest}  {INSTALLER_NAME}\n".encode()
        opener = FakeOpener([checksum, installer])
        with tempfile.TemporaryDirectory() as folder:
            path = download_verified_installer(
                "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                "https://github.com/org/repo/releases/download/v1/" + CHECKSUM_NAME,
                folder, opener,
            )
            self.assertEqual(path.read_bytes(), installer)

    def test_rejects_tampered_installer(self):
        checksum = ("0" * 64 + "  " + INSTALLER_NAME + "\n").encode()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                download_verified_installer(
                    "https://github.com/org/repo/releases/download/v1/" + INSTALLER_NAME,
                    "https://github.com/org/repo/releases/download/v1/" + CHECKSUM_NAME,
                    folder, FakeOpener([checksum, b"tampered"]),
                )
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_rejects_non_github_download_url(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                download_verified_installer(
                    "https://example.com/" + INSTALLER_NAME,
                    "https://github.com/org/repo/" + CHECKSUM_NAME,
                    folder,
                )


if __name__ == "__main__":
    unittest.main()
