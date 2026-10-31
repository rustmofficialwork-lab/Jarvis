"""HTTPS-only GitHub Releases updater with SHA-256 verification."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

API_URL = "https://api.github.com/repos/rustmofficialwork-lab/Jarvis/releases/latest"
INSTALLER_NAME = "JARVIS-Setup-x64.exe"
CHECKSUM_NAME = "SHA256SUMS.txt"
MAX_API_BYTES = 1024 * 1024
MAX_CHECKSUM_BYTES = 16 * 1024
MAX_INSTALLER_BYTES = 200 * 1024 * 1024
ALLOWED_REDIRECT_HOSTS = {
    "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
}


def _version_tuple(value: str) -> tuple[int, ...]:
    normalized = str(value).strip().removeprefix("v")
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", normalized):
        raise ValueError("The release version is not a valid numeric version.")
    return tuple(int(part) for part in normalized.split("."))


def _safe_github_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
        raise ValueError("The update release contains an unsafe download URL.")
    return value


def _open(url: str, timeout: int, opener=None):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "JARVIS-Desktop-Updater", "Accept": "application/vnd.github+json"},
    )
    if opener is not None:
        return opener(request, timeout=timeout)

    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urlparse(newurl)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_REDIRECT_HOSTS:
                return None
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(SafeRedirect).open(request, timeout=timeout)


def _read_limited(response, maximum: int) -> bytes:
    data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("The update server returned a file larger than the safety limit.")
    return data


def check_for_update(current_version: str, opener=None) -> dict:
    """Check the public latest GitHub release; never downloads or runs anything."""
    current = _version_tuple(current_version)
    try:
        with _open(API_URL, timeout=12, opener=opener) as response:
            payload = json.loads(_read_limited(response, MAX_API_BYTES).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"available": False, "release_exists": False, "current_version": current_version}
        raise RuntimeError(f"GitHub update check returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not check for updates: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("GitHub returned an invalid update description.") from exc

    tag = payload.get("tag_name", "")
    latest = _version_tuple(tag)
    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("The GitHub release has an invalid asset list.")
    by_name = {
        item.get("name"): item for item in assets
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    installer = by_name.get(INSTALLER_NAME)
    checksums = by_name.get(CHECKSUM_NAME)
    if latest > current and (not installer or not checksums):
        raise RuntimeError("A newer release exists, but its verified installer assets are incomplete.")

    return {
        "available": latest > current,
        "release_exists": True,
        "current_version": current_version,
        "latest_version": ".".join(str(part) for part in latest),
        "tag": tag,
        "release_url": payload.get("html_url", "https://github.com/rustmofficialwork-lab/Jarvis/releases"),
        "installer_url": _safe_github_url(installer.get("browser_download_url")) if installer else None,
        "checksums_url": _safe_github_url(checksums.get("browser_download_url")) if checksums else None,
    }


def download_verified_installer(installer_url: str, checksums_url: str,
                                destination_dir: str | Path, opener=None) -> Path:
    """Download the release installer only after matching its published SHA-256."""
    installer_url = _safe_github_url(installer_url)
    checksums_url = _safe_github_url(checksums_url)
    try:
        with _open(checksums_url, timeout=20, opener=opener) as response:
            checksum_text = _read_limited(response, MAX_CHECKSUM_BYTES).decode("utf-8", errors="strict")
        match = re.search(
            rf"(?im)^([0-9a-f]{{64}})\s+\*?{re.escape(INSTALLER_NAME)}\s*$",
            checksum_text,
        )
        if not match:
            raise ValueError("The release checksum file does not contain the expected installer hash.")
        expected = match.group(1).lower()
        with _open(installer_url, timeout=60, opener=opener) as response:
            installer_bytes = _read_limited(response, MAX_INSTALLER_BYTES)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not download the JARVIS update: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("The release checksum file is not valid UTF-8.") from exc

    actual = hashlib.sha256(installer_bytes).hexdigest()
    if actual != expected:
        raise ValueError("The installer SHA-256 check failed. The downloaded file was not kept.")

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    final_path = destination / INSTALLER_NAME
    temporary = destination / (INSTALLER_NAME + ".download")
    try:
        temporary.write_bytes(installer_bytes)
        temporary.replace(final_path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return final_path
