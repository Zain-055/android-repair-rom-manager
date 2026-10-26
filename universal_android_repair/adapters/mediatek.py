from __future__ import annotations

from .base import AdapterSupportProfile, DeviceAdapter


class MediaTekAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="MediaTek",
        platform="MediaTek Helio / Dimensity",
        chipset_family="MediaTek",
        supported_communication_protocols=["adb", "fastboot", "mtk-client"],
        supported_device_models=["Pova series", "Dimensity devices"],
        required_drivers=["MediaTek USB VCOM drivers"],
        firmware_formats=["scatter", "fastboot", "recovery-zip"],
        installation_requirements="Scatter packages require exact variant matching and verified metadata before flashing.",
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        return "mediatek" in platform or "dimensity" in chipset or "helio" in chipset
