from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "Compatible"
    CONDITIONALLY_COMPATIBLE = "Conditionally compatible"
    UNVERIFIED = "Unverified"
    INCOMPATIBLE = "Incompatible"


@dataclass
class FirmwarePackage:
    name: str
    manufacturer: str
    model: str
    codename: str
    chipset: str
    platform: str
    package_type: str
    installation_method: str
    android_version: str
    source: str
    official: bool = True
    sha256: str = "unknown"
    signature_status: str = "not checked"
    verification_status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FirmwarePackage":
        package = cls(
            name=data.get("name", "unnamed"),
            manufacturer=data.get("manufacturer", "Unknown"),
            model=data.get("model", "Unknown"),
            codename=data.get("codename", "unknown"),
            chipset=data.get("chipset", "Unknown"),
            platform=data.get("platform", "Unknown"),
            package_type=data.get("package_type", "factory-image"),
            installation_method=data.get("installation_method", "fastboot"),
            android_version=data.get("android_version", "Unknown"),
            source=data.get("source", "manual"),
            official=bool(data.get("official", True)),
            sha256=data.get("sha256", "unknown"),
            signature_status=data.get("signature_status", "not checked"),
            verification_status=data.get("verification_status", "pending"),
            metadata=data.get("metadata", {}),
        )
        return package


@dataclass
class CompatibilityReport:
    status: CompatibilityStatus
    messages: list[str]


class FirmwareManager:
    def __init__(self, manifest_path: str | Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.manifest_path = Path(manifest_path) if manifest_path else base_dir / "config" / "firmware_manifest.json"
        self.packages = self.load_manifest()

    def load_manifest(self) -> list[FirmwarePackage]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        manifest_items = payload.get("firmware", [])
        return [FirmwarePackage.from_mapping(item) for item in manifest_items]

    def verify_compatibility(self, device: Any, firmware: FirmwarePackage) -> CompatibilityReport:
        messages: list[str] = []

        device_manufacturer = getattr(device, "manufacturer", "Not detected")
        device_model = getattr(device, "model", "Not detected")
        device_codename = getattr(device, "codename", "Not detected")
        device_chipset = getattr(device, "chipset", "Not detected")
        device_platform = getattr(device, "platform", "Not detected")
        device_bootloader = getattr(device, "bootloader_state", "Not detected")

        if device_model == "Not detected" and device_codename == "Not detected":
            return CompatibilityReport(CompatibilityStatus.UNVERIFIED, ["Device identity is incomplete. Manual verification is required."])

        if firmware.model.lower() != device_model.lower() and firmware.codename.lower() != device_codename.lower():
            return CompatibilityReport(CompatibilityStatus.INCOMPATIBLE, [
                f"Firmware {firmware.model} does not match detected device {device_model}.",
                "Model or codename mismatch detected.",
            ])

        if firmware.chipset.lower() != device_chipset.lower() and device_chipset != "Not detected":
            return CompatibilityReport(CompatibilityStatus.INCOMPATIBLE, [
                f"Chipset mismatch: firmware expects {firmware.chipset}, detected {device_chipset}.",
            ])

        if firmware.platform.lower() != device_platform.lower() and device_platform != "Not detected":
            return CompatibilityReport(CompatibilityStatus.INCOMPATIBLE, [
                f"Platform mismatch: firmware targets {firmware.platform}, detected {device_platform}.",
            ])

        if firmware.signature_status.lower() == "missing":
            return CompatibilityReport(CompatibilityStatus.UNVERIFIED, [
                "The firmware package is missing the required signature metadata.",
            ])

        if (
            firmware.signature_status.lower() != "verified"
            or firmware.verification_status.lower() != "verified"
            or not re.fullmatch(r"[0-9a-fA-F]{64}", firmware.sha256)
        ):
            return CompatibilityReport(CompatibilityStatus.UNVERIFIED, [
                "The package checksum and signature have not been verified.",
                "Download the package from an official source and verify its published checksum before installation.",
            ])

        if firmware.official is False:
            messages.append("This is a community-maintained package. Confirm the source and checksum before installation.")

        if device_bootloader.lower() == "locked" and firmware.package_type == "custom-rom":
            return CompatibilityReport(CompatibilityStatus.CONDITIONALLY_COMPATIBLE, [
                "Bootloader is locked. This application installs custom ROMs only when it is already unlocked.",
                "No bootloader-unlock or account-protection bypass operation is provided.",
            ])

        messages.append("Firmware package and device metadata are aligned.")
        return CompatibilityReport(CompatibilityStatus.COMPATIBLE, messages)

    def find_package_for_device(self, device: Any) -> list[FirmwarePackage]:
        matches: list[FirmwarePackage] = []
        for package in self.packages:
            if package.model.lower() == device.model.lower() or package.codename.lower() == device.codename.lower():
                matches.append(package)
        return matches
