from __future__ import annotations

import re

from .base import AdapterSupportProfile, DeviceAdapter


class MediaTekAdapter(DeviceAdapter):
    profile = AdapterSupportProfile(
        manufacturer="MediaTek",
        platform="MediaTek Helio / Dimensity",
        chipset_family="MediaTek",
        supported_communication_protocols=["ADB; Fastboot availability is model-dependent"],
        supported_device_models=[
            "TECNO devices",
            "vivo devices",
            "Infinix devices",
            "OPPO devices",
            "Other MediaTek-powered Android devices",
        ],
        required_drivers=["Use the device manufacturer's official driver guidance"],
        firmware_formats=["Vendor- and model-specific; not validated by this adapter"],
        installation_requirements=(
            "This adapter identifies MediaTek SoCs only. Firmware and flashing support must be "
            "validated for the exact device model and variant."
        ),
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        chipset = str(device_info.get("chipset", "")).lower()
        platform = str(device_info.get("platform", "")).lower()
        return (
            "mediatek" in platform
            or "mediatek" in chipset
            or "dimensity" in chipset
            or "helio" in chipset
            or bool(re.search(r"\bmtk?\s*-?\d{4,6}[a-z0-9]*\b", chipset))
        )
