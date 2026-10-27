from __future__ import annotations

import re
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .official_downloads import DownloadError, verify_android_package_device, verify_downloaded_file
from .process_utils import run_hidden


SUPPORTED_PIXEL_CODENAMES = {"shiba", "tokay"}
LINEAGEOS_IMAGES = ("boot.img", "dtbo.img", "vendor_kernel_boot.img", "vendor_boot.img")
GOOGLE_DOWNLOAD_HOSTS = {"dl.google.com"}
LINEAGEOS_DOWNLOAD_HOSTS = {"mirrorbits.lineageos.org", "download.lineageos.org"}


@dataclass
class FlashingWorkflow:
    title: str
    warnings: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    safe_to_proceed: bool = False


def build_stock_rom_plan(device: Any, firmware: Any) -> FlashingWorkflow:
    warnings = [
        "Factory reset and data loss risk: back up user data before continuing.",
        "Verify the device model, firmware package, and bootloader state again before flashing.",
    ]
    procedures = [
        "Validate device identity and firmware hashes.",
        "Confirm ADB/Fastboot authorization state and required drivers are installed.",
        "Flash only compatible partitions using the official vendor workflow.",
        "Verify the device after installation and report any post-flash issues.",
    ]
    return FlashingWorkflow(
        title=f"Stock ROM install for {device.model}",
        warnings=warnings,
        procedures=procedures,
        requires_confirmation=True,
        safe_to_proceed=True,
    )


def build_custom_rom_plan(device: Any, rom: Any) -> FlashingWorkflow:
    warnings = [
        "Custom ROM installation may erase userdata and requires a bootloader that is already unlocked.",
        "Only install a ROM supported by the exact model and codename.",
        "Verify the ROM's checksums and installation instructions before flashing.",
    ]
    procedures = [
        "Check whether the device codename and build baseline are officially supported.",
        "Confirm the bootloader is already unlocked; this application will not unlock it.",
        "Validate recovery and rollback requirements.",
        "Use the ROM project's documented installation procedure.",
        "Perform a first-boot verification and capture any recovery steps.",
    ]
    return FlashingWorkflow(
        title=f"Custom ROM install for {device.model}",
        warnings=warnings,
        procedures=procedures,
        requires_confirmation=True,
        safe_to_proceed=device.bootloader_state.lower() == "unlocked",
    )


class FlashingError(RuntimeError):
    """Raised when a guarded firmware installation cannot be completed."""


def flash_google_stock_ota(device: Any, package_path: str | Path) -> None:
    codename = _validate_pixel_device(device)
    _run_adb_sideload(
        device.serial_number,
        Path(package_path),
        codename,
        GOOGLE_DOWNLOAD_HOSTS,
    )


def flash_lineageos_images(
    device: Any,
    image_directory: str | Path,
    package_path: str | Path,
) -> None:
    codename = _validate_pixel_device(device)
    _verify_download(package_path, LINEAGEOS_DOWNLOAD_HOSTS, codename)
    try:
        verify_android_package_device(package_path, codename)
    except DownloadError as error:
        raise FlashingError(str(error)) from error
    if str(device.bootloader_state).lower() != "unlocked":
        raise FlashingError("LineageOS flashing is allowed only when the bootloader is already unlocked.")
    if not device.fastboot_available:
        raise FlashingError("The Pixel must be connected in Fastboot mode.")

    image_root = Path(image_directory)
    missing = [filename for filename in LINEAGEOS_IMAGES if not (image_root / filename).is_file()]
    if missing:
        raise FlashingError(f"Missing official LineageOS image files: {', '.join(missing)}.")
    for filename in LINEAGEOS_IMAGES:
        _verify_download(image_root / filename, LINEAGEOS_DOWNLOAD_HOSTS, codename)
    serial = _device_serial(device)
    fastboot = shutil.which("fastboot")
    if not fastboot:
        raise FlashingError("Fastboot was not found on PATH.")
    _verify_fastboot_pixel(fastboot, serial, codename)

    for partition, filename in (
        ("boot", "boot.img"),
        ("dtbo", "dtbo.img"),
        ("vendor_kernel_boot", "vendor_kernel_boot.img"),
    ):
        _run_checked([fastboot, "-s", serial, "flash", partition, str(image_root / filename)])
    _run_checked([fastboot, "-s", serial, "reboot", "bootloader"])
    _wait_for_fastboot_device(fastboot, serial, codename)
    _run_checked([fastboot, "-s", serial, "flash", "vendor_boot", str(image_root / "vendor_boot.img")])


def sideload_lineageos_package(device: Any, package_path: str | Path) -> None:
    codename = _validate_pixel_device(device)
    _run_adb_sideload(
        device.serial_number,
        Path(package_path),
        codename,
        LINEAGEOS_DOWNLOAD_HOSTS,
        codename,
    )


def _validate_pixel_device(device: Any) -> str:
    codename = str(getattr(device, "codename", "")).lower()
    manufacturer = str(getattr(device, "manufacturer", "")).lower()
    if manufacturer != "google" or codename not in SUPPORTED_PIXEL_CODENAMES:
        raise FlashingError("Only supported Google Pixel 8 (shiba) and Pixel 9 (tokay) devices are enabled.")
    return codename


def _device_serial(device: Any) -> str:
    serial = str(getattr(device, "serial_number", ""))
    if not serial or serial == "Not detected":
        raise FlashingError("A device serial number is required; refusing to run an un-targeted flash command.")
    return serial


def _verify_fastboot_pixel(fastboot: str, serial: str, codename: str) -> None:
    product = _run_checked([fastboot, "-s", serial, "getvar", "product"], allow_stderr=True)
    unlocked = _run_checked([fastboot, "-s", serial, "getvar", "unlocked"], allow_stderr=True)
    if not re.search(rf"product:\s*{re.escape(codename)}\b", product, re.IGNORECASE):
        raise FlashingError("The connected Fastboot product does not match the selected Pixel.")
    if not re.search(r"unlocked:\s*(yes|true|1)\b", unlocked, re.IGNORECASE):
        raise FlashingError("The connected bootloader is not confirmed unlocked; no partitions were flashed.")


def _wait_for_fastboot_device(fastboot: str, serial: str, codename: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            result = run_hidden(
                [fastboot, "devices"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            time.sleep(1)
            continue
        except OSError as error:
            raise FlashingError(f"Could not restart Fastboot after reboot: {error}") from error
        if result.returncode == 0 and re.search(
            rf"^{re.escape(serial)}(?:\s|$)",
            result.stdout,
            re.MULTILINE,
        ):
            _verify_fastboot_pixel(fastboot, serial, codename)
            return
        time.sleep(1)
    raise FlashingError("The Pixel did not return to Fastboot after reboot; no further partition was flashed.")


def _run_adb_sideload(
    serial: str,
    package_path: Path,
    codename: str,
    allowed_hosts: set[str],
    expected_codename: str | None = None,
) -> None:
    serial = str(serial)
    if not package_path.is_file():
        raise FlashingError("Select an existing OTA package.")
    _verify_download(package_path, allowed_hosts, expected_codename)
    try:
        verify_android_package_device(package_path, codename)
    except DownloadError as error:
        raise FlashingError(str(error)) from error

    adb = shutil.which("adb")
    if not adb:
        raise FlashingError("ADB was not found on PATH.")
    devices = _run_checked([adb, "devices"])
    if not serial or serial == "Not detected":
        sideload_devices = re.findall(r"^(\S+)\s+sideload$", devices, re.MULTILINE)
        if len(sideload_devices) != 1:
            raise FlashingError(
                "A device serial number is required; connect exactly one Pixel in Recovery's Apply from ADB mode."
            )
        serial = sideload_devices[0]
    if not re.search(rf"^{re.escape(serial)}\s+sideload$", devices, re.MULTILINE):
        raise FlashingError("Put the matching Pixel into Recovery > Apply update > Apply from ADB first.")
    _run_checked([adb, "-s", serial, "sideload", str(package_path)])


def _verify_download(
    package_path: str | Path,
    allowed_hosts: set[str],
    expected_codename: str | None = None,
) -> None:
    try:
        source_url = verify_downloaded_file(package_path)
    except DownloadError as error:
        raise FlashingError(str(error)) from error
    if urllib.parse.urlparse(source_url).hostname not in allowed_hosts:
        raise FlashingError("The package was not downloaded from the expected official vendor.")
    if expected_codename:
        source_path = urllib.parse.unquote(urllib.parse.urlparse(source_url).path)
        if not re.search(
            rf"(?<![a-z0-9]){re.escape(expected_codename)}(?![a-z0-9])",
            source_path,
            re.IGNORECASE,
        ):
            raise FlashingError("The LineageOS download URL does not identify the selected Pixel codename.")


def _run_checked(command: list[str], allow_stderr: bool = False) -> str:
    try:
        result = run_hidden(
            command,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise FlashingError(f"{Path(command[0]).name} timed out.") from error
    except OSError as error:
        raise FlashingError(f"Could not start {Path(command[0]).name}: {error}") from error

    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0 and not allow_stderr:
        raise FlashingError(output.strip() or f"{Path(command[0]).name} exited with status {result.returncode}.")
    if not output.strip() and result.returncode != 0:
        raise FlashingError(f"{Path(command[0]).name} exited with status {result.returncode}.")
    return output
