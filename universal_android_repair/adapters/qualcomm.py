from __future__ import annotations

from .base import AdapterSupportProfile, DeviceAdapter


class QualcommAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="Qualcomm",
        platform="Qualcomm Snapdragon",
        chipset_family="Snapdragon",
        supported_communication_protocols=["adb", "fastboot"],
        supported_device_models=["OnePlus 12", "Pixel 8"],
        required_drivers=["Qualcomm USB drivers"],
        firmware_formats=["fastboot", "factory-image", "OTA"],
        installation_requirements="Use an official factory image or project-maintained fastboot package, then require user approval before flashing.",
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        return "snapdragon" in platform or "qualcomm" in platform or "snapdragon" in chipset
