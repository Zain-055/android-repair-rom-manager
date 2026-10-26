from __future__ import annotations

from .base import AdapterSupportProfile, DeviceAdapter


class GoogleTensorAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="Google",
        platform="Google Tensor",
        chipset_family="Tensor",
        supported_communication_protocols=["adb", "fastboot"],
        supported_device_models=["Pixel 8", "Pixel 9"],
        required_drivers=["Google USB drivers"],
        firmware_formats=["factory-image", "fastboot"],
        installation_requirements="Use verified factory images from Google or trusted project-maintained sources only.",
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        return "tensor" in chipset or "tensor" in platform or "google" in str(device_info.get("manufacturer", "")).lower()
