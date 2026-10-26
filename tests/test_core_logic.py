from universal_android_repair.core.database import DatabaseManager
from universal_android_repair.core.detection import DeviceDetectionEngine
from universal_android_repair.core.device_connection import AndroidDeviceConnector
from universal_android_repair.core.firmware import CompatibilityStatus, FirmwareManager
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


def test_resource_catalog_returns_vendor_and_processor_links():
    firmware = firmware_sources("Google")
    drivers = driver_sources("Google", "Qualcomm Snapdragon 8 Gen 3")

    assert firmware[0][1] == "https://developers.google.com/android/images"
    assert any("Google USB driver" == label for label, _ in drivers)
    assert any("Qualcomm support" == label for label, _ in drivers)


def test_frozen_database_uses_persistent_user_data_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("universal_android_repair.core.database.sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    database = DatabaseManager()

    assert database.db_path == tmp_path / "UniversalAndroidRepair" / "repair_manager.db"
    assert database.db_path.exists()
