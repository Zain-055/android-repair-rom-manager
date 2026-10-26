from __future__ import annotations

from .base import AdapterSupportProfile, DeviceAdapter


class UnisocAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="Unisoc",
        platform="Unisoc",
        chipset_family="Unisoc",
        supported_communication_protocols=["adb", "fastboot"],
        supported_device_models=["Entry-level devices"],
        required_drivers=["USB serial drivers"],
        firmware_formats=["factory-image", "recovery-zip"],
        installation_requirements="Only use verified vendor packages and confirm market-specific firmware parity before flashing.",
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        return "unisoc" in chipset or "unisoc" in platform
