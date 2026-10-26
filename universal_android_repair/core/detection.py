from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .device_profiles import DeviceProfile, find_matching_profile, load_device_profiles


@dataclass
class DeviceDetection:
    manufacturer: str = "Not detected"
    model: str = "Not detected"
    codename: str = "Not detected"
    platform: str = "Not detected"
    chipset: str = "Not detected"
    cpu_architecture: str = "Not detected"
    android_version: str = "Not detected"
    build_fingerprint: str = "Not detected"
    bootloader_state: str = "Not detected"
    adb_authorized: bool = False
    fastboot_available: bool = False
    usb_vendor_id: str = "Not detected"
    usb_product_id: str = "Not detected"
    serial_number: str = "Not detected"
    identification_sources: list[str] = field(default_factory=list)
    profile: DeviceProfile | None = None


class DeviceDetectionEngine:
    def __init__(self, profiles: list[DeviceProfile] | None = None) -> None:
        self.profiles = profiles if profiles is not None else load_device_profiles()

    def detect(self, raw: dict[str, Any]) -> DeviceDetection:
        detection = DeviceDetection()
        adb = raw.get("adb", {}) if isinstance(raw.get("adb", {}), dict) else {}
        fastboot = raw.get("fastboot", {}) if isinstance(raw.get("fastboot", {}), dict) else {}
        usb = raw.get("usb", {}) if isinstance(raw.get("usb", {}), dict) else {}

        detection.manufacturer = str(adb.get("manufacturer") or usb.get("manufacturer") or "Not detected")
        detection.model = str(adb.get("model") or fastboot.get("device") or usb.get("model") or "Not detected")
        detection.codename = str(adb.get("codename") or fastboot.get("codename") or "Not detected")
        detection.platform = str(adb.get("platform") or fastboot.get("platform") or "Not detected")
        detection.chipset = str(adb.get("chipset") or fastboot.get("chipset") or "Not detected")
        detection.cpu_architecture = str(adb.get("cpu_architecture") or fastboot.get("cpu_architecture") or "Not detected")
        detection.android_version = str(adb.get("android_version") or fastboot.get("android_version") or "Not detected")
        detection.build_fingerprint = str(adb.get("build_fingerprint") or fastboot.get("build_fingerprint") or "Not detected")
        detection.bootloader_state = str(adb.get("bootloader_state") or fastboot.get("bootloader_state") or "Not detected")
        detection.adb_authorized = bool(adb.get("adb_authorized"))
        detection.fastboot_available = bool(fastboot.get("available") or adb.get("fastboot_available"))
        detection.usb_vendor_id = str(usb.get("vendor_id") or "Not detected")
        detection.usb_product_id = str(usb.get("product_id") or "Not detected")
        detection.serial_number = str(adb.get("serial") or fastboot.get("serial") or usb.get("serial") or "Not detected")

        if adb:
            detection.identification_sources.append("ADB properties")
        if fastboot:
            detection.identification_sources.append("Fastboot variables")
        if usb:
            detection.identification_sources.append("USB identifiers")
        if not detection.identification_sources:
            detection.identification_sources = ["Manual profile selection"]

        detection.profile = self._resolve_profile(detection)
        if detection.profile:
            if detection.manufacturer == "Not detected":
                detection.manufacturer = detection.profile.manufacturer
            if detection.chipset == "Not detected":
                detection.chipset = detection.profile.chipset
            if detection.platform == "Not detected":
                detection.platform = detection.profile.platform
        return detection

    def _resolve_profile(self, detection: DeviceDetection) -> DeviceProfile | None:
        candidate_names = [detection.model, detection.codename, detection.manufacturer]
        for value in candidate_names:
            profile = find_matching_profile(value, self.profiles)
            if profile:
                return profile

        if detection.manufacturer.lower() == "google" and "pixel" in detection.model.lower():
            for profile in self.profiles:
                if profile.manufacturer.lower() == "google":
                    return profile
        if detection.manufacturer.lower() == "samsung" and "galaxy" in detection.model.lower():
            for profile in self.profiles:
                if profile.manufacturer.lower() == "samsung":
                    return profile
        return None

    def compatibility_summary(self, device: DeviceDetection) -> str:
        if device.profile:
            return f"{device.manufacturer} {device.model} matched profile {device.profile.model} ({device.profile.platform})"
        return "Device profile not matched; manual verification required."
