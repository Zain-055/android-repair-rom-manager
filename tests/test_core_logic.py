import hashlib
import io
import subprocess
import zipfile
from unittest.mock import patch

import pytest

from universal_android_repair.core.database import DatabaseManager
from universal_android_repair.core.detection import DeviceDetectionEngine
from universal_android_repair.core.device_connection import AndroidDeviceConnector
from universal_android_repair.adapters.mediatek import MediaTekAdapter
from universal_android_repair.core.firmware import CompatibilityStatus, FirmwareManager
from universal_android_repair.core.flashing import (
    FlashingError,
    _validate_pixel_device,
    build_custom_rom_plan,
    flash_lineageos_images,
)
from universal_android_repair.core.official_downloads import (
    DownloadError,
    download_official_package,
    validate_official_url,
    verify_android_package_device,
    verify_downloaded_file,
)
from universal_android_repair.core import process_utils
from universal_android_repair.core.resource_catalog import driver_sources, firmware_sources


def test_detection_matches_profile():
    engine = DeviceDetectionEngine()
    detected = engine.detect({
        "adb": {"manufacturer": "Google", "model": "Pixel 8", "codename": "shiba", "chipset": "Google Tensor G3", "platform": "Google Tensor"},
        "fastboot": {"available": True, "bootloader_state": "locked"},
    })
    assert detected.profile is not None
    assert detected.profile.model == "Pixel 8"


def test_firmware_compatibility_checks():
    manager = FirmwareManager()
    device = type("Device", (), {"model": "Pixel 8", "codename": "shiba", "chipset": "Google Tensor G3", "platform": "Google Tensor", "bootloader_state": "locked"})()
    package = manager.packages[0]

    report = manager.verify_compatibility(device, package)
    assert report.status == CompatibilityStatus.UNVERIFIED

    package.sha256 = "a" * 64
    package.signature_status = "verified"
    package.verification_status = "verified"
    report = manager.verify_compatibility(device, package)
    assert report.status == CompatibilityStatus.COMPATIBLE


def test_unmatched_device_is_unverified():
    manager = FirmwareManager()
    device = type("Device", (), {"model": "Unknown Phone", "codename": "unknown", "chipset": "Unknown", "platform": "Unknown", "bootloader_state": "locked"})()
    package = manager.packages[2]
    report = manager.verify_compatibility(device, package)
    assert report.status in {CompatibilityStatus.INCOMPATIBLE, CompatibilityStatus.UNVERIFIED}


def test_device_connection_parses_adb_and_fastboot_device_lists():
    adb_devices = AndroidDeviceConnector._parse_adb_devices(
        "List of devices attached\nemulator-5554 device product:device model:Pixel_8\nphone offline\n"
    )
    fastboot_devices = AndroidDeviceConnector._parse_fastboot_devices("phone\tfastboot\n")

    assert adb_devices == [("emulator-5554", "device"), ("phone", "offline")]
    assert fastboot_devices == ["phone"]


def test_windows_subprocesses_are_started_without_console_windows(monkeypatch):
    startupinfo = type("StartupInfo", (), {"dwFlags": 0, "wShowWindow": 0})()
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(process_utils.sys, "platform", "win32")
    monkeypatch.setattr(process_utils.subprocess, "STARTUPINFO", lambda: startupinfo, raising=False)
    monkeypatch.setattr(process_utils.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(process_utils.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(process_utils.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(process_utils.subprocess, "run", fake_run)

    process_utils.run_hidden(["adb", "devices"], capture_output=True, text=True)

    assert captured["startupinfo"] is startupinfo
    assert startupinfo.dwFlags & 1
    assert startupinfo.wShowWindow == 0
    assert captured["creationflags"] == 0x08000000


def test_device_connection_maps_android_properties():
    mapped = AndroidDeviceConnector._map_adb_properties(
        {
            "ro.product.manufacturer": "Google",
            "ro.product.model": "Pixel 8",
            "ro.product.device": "shiba",
            "ro.soc.model": "Tensor G3",
            "ro.build.version.release": "14",
            "ro.boot.flash.locked": "1",
        }
    )

    assert mapped["manufacturer"] == "Google"
    assert mapped["model"] == "Pixel 8"
    assert mapped["codename"] == "shiba"
    assert mapped["chipset"] == "Tensor G3"
    assert mapped["bootloader_state"] == "locked"


def test_profile_fills_missing_chipset_and_platform():
    device = DeviceDetectionEngine().detect(
        {"adb": {"manufacturer": "Google", "model": "Pixel 8", "codename": "shiba"}}
    )

    assert device.chipset == "Google Tensor G3"
    assert device.platform == "Google Tensor"


@pytest.mark.parametrize(
    ("raw_manufacturer", "expected_manufacturer", "firmware_url"),
    [
        ("TECNO MOBILE LIMITED", "TECNO", "https://www.tecno-mobile.com/support/"),
        ("vivo", "vivo", "https://www.vivo.com/en/support"),
        ("INFINIX MOBILITY LIMITED", "Infinix", "https://www.carlcare.com/"),
        (
            "OPPO Mobile Telecommunications Corp.",
            "OPPO",
            "https://support.oppo.com/",
        ),
    ],
)
def test_mediatek_oem_detection_and_official_resources(
    raw_manufacturer,
    expected_manufacturer,
    firmware_url,
):
    device = DeviceDetectionEngine().detect(
        {
            "adb": {
                "manufacturer": raw_manufacturer,
                "model": "Example model",
                "chipset": "MTK6769V",
            }
        }
    )

    assert device.manufacturer == expected_manufacturer
    assert device.chipset == "MTK6769V"
    assert device.platform == "MediaTek"
    assert device.profile is None
    assert firmware_sources(device.manufacturer)[0][1] == firmware_url
    assert MediaTekAdapter.detect({"chipset": device.chipset, "platform": device.platform})


def test_mediatek_resources_and_adapter_recognize_named_chipsets():
    tecno_firmware = firmware_sources("TECNO")
    infinix_firmware = firmware_sources("Infinix")
    drivers = driver_sources("OPPO Mobile Telecommunications Corp.", "MTK6769")

    assert tecno_firmware[0][1] == "https://www.tecno-mobile.com/support/"
    assert (
        "TECNO Firmware catalog (third-party)",
        "https://tecnofirmware.com/",
    ) in tecno_firmware
    assert infinix_firmware[0][1] == "https://www.carlcare.com/"
    assert (
        "Infinix firmware search (third-party catalog)",
        "https://tecnofirmware.com/",
    ) in infinix_firmware
    assert ("MediaTek chipset information", "https://www.mediatek.com/") in drivers
    assert MediaTekAdapter.detect({"chipset": "Dimensity 8300"})
    assert MediaTekAdapter.detect({"chipset": "Helio G99"})


def test_fastboot_product_matches_pixel_profile():
    device = DeviceDetectionEngine().detect(
        {"fastboot": {"available": True, "device": "shiba", "bootloader_state": "unlocked", "serial": "pixel"}}
    )

    assert device.profile is not None
    assert device.model == "Pixel 8"
    assert device.codename == "shiba"


def test_tecno_camon_19_neo_is_matched_by_model_code_alias():
    device = DeviceDetectionEngine().detect(
        {
            "adb": {
                "manufacturer": "TECNO MOBILE LIMITED",
                "model": "TECNO CH6i",
                "codename": "CH6i",
                "chipset": "MTK",
            }
        }
    )

    assert device.profile is not None
    assert device.profile.model == "TECNO Camon 19 Neo"
    assert device.manufacturer == "TECNO"
    assert device.platform == "MediaTek"
    assert device.profile.firmware_formats == []


def test_resource_catalog_returns_vendor_and_processor_links():
    firmware = firmware_sources("Google")
    drivers = driver_sources("Google", "Qualcomm Snapdragon 8 Gen 3")

    assert firmware[0][1] == "https://developers.google.com/android/images"
    assert any("Google USB driver" == label for label, _ in drivers)
    assert any("Qualcomm support" == label for label, _ in drivers)


def test_adb_sideload_mode_is_parsed():
    assert AndroidDeviceConnector._parse_adb_devices(
        "List of devices attached\npixel-serial sideload\n"
    ) == [("pixel-serial", "sideload")]


def test_official_package_url_requires_https_and_allowlisted_host():
    validate_official_url("https://dl.google.com/android/repository/package.zip")
    validate_official_url("https://mirrorbits.lineageos.org/full/shiba/build.zip")

    with pytest.raises(DownloadError):
        validate_official_url("http://dl.google.com/package.zip")
    with pytest.raises(DownloadError):
        validate_official_url("https://example.com/package.zip")


def test_official_download_checks_sha256_and_records_verified_file(tmp_path):
    payload = b"official firmware test payload"

    class Response(io.BytesIO):
        def geturl(self):
            return "https://dl.google.com/android/repository/package.zip"

    class Opener:
        def open(self, request, timeout):
            return Response(payload)

    destination = tmp_path / "package.zip"
    checksum = hashlib.sha256(payload).hexdigest()
    with patch(
        "universal_android_repair.core.official_downloads.urllib.request.build_opener",
        return_value=Opener(),
    ):
        assert download_official_package(
            "https://dl.google.com/android/repository/package.zip",
            destination,
            checksum,
        ) == destination

    verify_downloaded_file(destination)
    destination.write_bytes(b"modified")
    with pytest.raises(DownloadError, match="no longer matches"):
        verify_downloaded_file(destination)


def test_ota_package_device_metadata_must_match(tmp_path):
    package_path = tmp_path / "pixel-ota.zip"
    with zipfile.ZipFile(package_path, "w") as package:
        package.writestr("META-INF/com/android/metadata", "pre-device=shiba,tokay\n")

    verify_android_package_device(package_path, "shiba")
    with pytest.raises(DownloadError, match="does not match"):
        verify_android_package_device(package_path, "sunfish")


def test_lineage_device_gate_accepts_only_supported_pixel_codenames():
    pixel = type("Device", (), {"manufacturer": "Google", "codename": "tokay"})()
    unsupported = type("Device", (), {"manufacturer": "Google", "codename": "sunfish"})()

    assert _validate_pixel_device(pixel) == "tokay"
    with pytest.raises(FlashingError, match="Only supported"):
        _validate_pixel_device(unsupported)


def test_custom_rom_plan_requires_explicitly_unlocked_bootloader():
    locked = type("Device", (), {"model": "Pixel 8", "bootloader_state": "locked"})()
    unknown = type("Device", (), {"model": "Pixel 8", "bootloader_state": "Not detected"})()
    unlocked = type("Device", (), {"model": "Pixel 8", "bootloader_state": "unlocked"})()

    assert not build_custom_rom_plan(locked, None).safe_to_proceed
    assert not build_custom_rom_plan(unknown, None).safe_to_proceed
    assert build_custom_rom_plan(unlocked, None).safe_to_proceed


def test_lineage_flash_refuses_locked_bootloader_before_running_fastboot(tmp_path, monkeypatch):
    images = ("boot.img", "dtbo.img", "vendor_kernel_boot.img", "vendor_boot.img")
    for filename in images:
        image_path = tmp_path / filename
        image_path.write_bytes(b"image")
        (tmp_path / f"{filename}.sha256").write_text(
            f"{hashlib.sha256(b'image').hexdigest()}\n"
            "https://mirrorbits.lineageos.org/full/shiba/build/image.img\n",
            encoding="ascii",
        )

    package_path = tmp_path / "lineage.zip"
    with zipfile.ZipFile(package_path, "w") as package:
        package.writestr("META-INF/com/android/metadata", "pre-device=shiba\n")
    package_hash = hashlib.sha256(package_path.read_bytes()).hexdigest()
    (tmp_path / "lineage.zip.sha256").write_text(
        f"{package_hash}\nhttps://mirrorbits.lineageos.org/full/shiba/build/lineage.zip\n",
        encoding="ascii",
    )
    device = type(
        "Device",
        (),
        {
            "manufacturer": "Google",
            "codename": "shiba",
            "bootloader_state": "locked",
            "fastboot_available": True,
            "serial_number": "pixel-serial",
        },
    )()
    monkeypatch.setattr(
        "universal_android_repair.core.flashing.shutil.which",
        lambda _: pytest.fail("Fastboot must not run for a locked bootloader"),
    )

    with pytest.raises(FlashingError, match="already unlocked"):
        flash_lineageos_images(device, tmp_path, package_path)


def test_frozen_database_uses_persistent_user_data_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("universal_android_repair.core.database.sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    database = DatabaseManager()

    assert database.db_path == tmp_path / "UniversalAndroidRepair" / "repair_manager.db"
    assert database.db_path.exists()
