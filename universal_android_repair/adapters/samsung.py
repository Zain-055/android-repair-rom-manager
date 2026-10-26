from __future__ import annotations

from .base import AdapterSupportProfile, DeviceAdapter


class SamsungAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="Samsung",
        platform="Samsung Exynos",
        chipset_family="Exynos",
        supported_communication_protocols=["adb", "odin", "fastboot"],
        supported_device_models=["Galaxy S24", "Galaxy Note", "Galaxy A series"],
        required_drivers=["Samsung USB drivers", "ODIN compatible drivers"],
        firmware_formats=["samsung-archive", "factory-image"],
        installation_requirements="Use authorized Samsung firmware and confirm the exact region, model, and bootloader requirements before installation.",
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        manufacturer = str(device_info.get("manufacturer", "")).lower()
        return "samsung" in manufacturer or "exynos" in chipset or "samsung exynos" in platform
