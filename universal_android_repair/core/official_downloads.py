from __future__ import annotations

import hashlib
import http.client
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


class DownloadError(RuntimeError):
    """Raised when an official package cannot be safely downloaded or verified."""


OFFICIAL_DOWNLOAD_HOSTS = {
    "dl.google.com",
    "mirrorbits.lineageos.org",
    "download.lineageos.org",
}


class _OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        validate_official_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def validate_official_url(url: str) -> None:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as error:
        raise DownloadError("The download URL is malformed.") from error
    try:
        port = parsed.port
    except ValueError as error:
        raise DownloadError("The download URL has an invalid port.") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in OFFICIAL_DOWNLOAD_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DownloadError("Use a direct HTTPS download URL from Google or LineageOS.")


def official_url_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_OfficialRedirectHandler())


def download_official_package(url: str, destination: str | Path, expected_sha256: str) -> Path:
    validate_official_url(url)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise DownloadError("A published 64-character SHA-256 checksum is required.")

    target = Path(destination)
    partial = target.with_name(f"{target.name}.part")
    checksum_file = target.with_name(f"{target.name}.sha256")
    partial_checksum = checksum_file.with_name(f"{checksum_file.name}.part")
    digest = hashlib.sha256()
    opener = official_url_opener()
    request = urllib.request.Request(url, headers={"User-Agent": "UniversalAndroidRepair/1.0"})

    try:
        with opener.open(request, timeout=30) as response, partial.open("wb") as output:
            final_url = response.geturl()
            validate_official_url(final_url)
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
        if digest.hexdigest().lower() != expected_sha256.lower():
            raise DownloadError("Downloaded file SHA-256 does not match the published checksum.")
        partial_checksum.write_text(f"{digest.hexdigest()}\n{url}\n", encoding="utf-8")
        os.replace(partial, target)
        os.replace(partial_checksum, checksum_file)
        return target
    except (OSError, urllib.error.URLError, TimeoutError, http.client.HTTPException) as error:
        partial.unlink(missing_ok=True)
        partial_checksum.unlink(missing_ok=True)
        raise DownloadError(f"Firmware download failed: {error}") from error
    except DownloadError:
        partial.unlink(missing_ok=True)
        partial_checksum.unlink(missing_ok=True)
        raise


def verify_downloaded_file(path: str | Path) -> str:
    package_path = Path(path)
    checksum_file = package_path.with_name(f"{package_path.name}.sha256")
    try:
        checksum_lines = checksum_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise DownloadError("Package was not downloaded and checksum-verified by this application.") from error
    expected = checksum_lines[0].strip().lower() if checksum_lines else ""
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise DownloadError("The saved package checksum record is invalid.")
    if len(checksum_lines) < 2:
        raise DownloadError("The saved package source record is missing.")
    source_url = checksum_lines[1].strip()
    validate_official_url(source_url)

    digest = hashlib.sha256()
    try:
        with package_path.open("rb") as package:
            while chunk := package.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise DownloadError(f"Could not verify the downloaded package: {error}") from error
    if digest.hexdigest() != expected:
        raise DownloadError("Package SHA-256 no longer matches the verified download record.")
    return source_url


def verify_android_package_device(package_path: str | Path, codename: str) -> None:
    try:
        with zipfile.ZipFile(package_path) as package:
            metadata_name = "META-INF/com/android/metadata"
            if metadata_name not in package.namelist():
                raise DownloadError("Package has no Android OTA device metadata; refusing to install it.")
            metadata = package.read(metadata_name).decode("utf-8", errors="replace")
    except DownloadError:
        raise
    except (OSError, UnicodeError, zipfile.BadZipFile, RuntimeError) as error:
        raise DownloadError(f"Could not inspect the Android OTA package: {error}") from error

    properties = dict(
        line.split("=", 1)
        for line in metadata.splitlines()
        if "=" in line
    )
    devices = {
        item.strip().lower()
        for item in properties.get("pre-device", "").split(",")
        if item.strip()
    }
    if codename.lower() not in devices:
        raise DownloadError(
            f"Package device metadata does not match the selected device ({codename})."
        )
