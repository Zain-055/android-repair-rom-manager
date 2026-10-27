from __future__ import annotations

import re

from .manufacturers import normalize_manufacturer


VENDOR_RESOURCES: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "google": {
        "firmware": (
            ("Google Pixel factory images", "https://developers.google.com/android/images"),
            ("Google Pixel OTA images", "https://developers.google.com/android/ota"),
            ("LineageOS Pixel 8 builds", "https://download.lineageos.org/devices/shiba/builds"),
            ("LineageOS Pixel 9 builds", "https://download.lineageos.org/devices/tokay/builds"),
            ("LineageOS Pixel 8 install guide", "https://wiki.lineageos.org/devices/shiba/install/"),
            ("LineageOS Pixel 9 install guide", "https://wiki.lineageos.org/devices/tokay/install/"),
        ),
        "drivers": (("Google USB driver", "https://developer.android.com/studio/run/win-usb"),),
    },
    "samsung": {
        "firmware": (("Samsung support and downloads", "https://www.samsung.com/us/support/downloads/"),),
        "drivers": (("Samsung Android USB driver", "https://developer.samsung.com/android-usb-driver"),),
    },
    "oneplus": {
        "firmware": (("OnePlus support", "https://service.oneplus.com/"),),
        "drivers": (("OnePlus support and downloads", "https://service.oneplus.com/"),),
    },
    "tecno": {
        "firmware": (
            ("TECNO official support and downloads", "https://www.tecno-mobile.com/support/"),
            ("TECNO Firmware catalog (third-party)", "https://tecnofirmware.com/"),
        ),
        "drivers": (("TECNO official support", "https://www.tecno-mobile.com/support/"),),
    },
    "vivo": {
        "firmware": (("vivo official support", "https://www.vivo.com/en/support"),),
        "drivers": (("vivo official support", "https://www.vivo.com/en/support"),),
    },
    "infinix": {
        "firmware": (
            ("Infinix official service and software support", "https://www.carlcare.com/"),
            ("Infinix firmware search (third-party catalog)", "https://tecnofirmware.com/"),
        ),
        "drivers": (("Infinix official service and software support", "https://www.carlcare.com/"),),
    },
    "oppo": {
        "firmware": (("OPPO official support", "https://support.oppo.com/"),),
        "drivers": (("OPPO official support", "https://support.oppo.com/"),),
    },
}

PROCESSOR_RESOURCES: dict[str, tuple[str, str]] = {
    "qualcomm": ("Qualcomm support", "https://www.qualcomm.com/support"),
    "mediatek": ("MediaTek chipset information", "https://www.mediatek.com/"),
    "dimensity": ("MediaTek chipset information", "https://www.mediatek.com/"),
    "helio": ("MediaTek chipset information", "https://www.mediatek.com/"),
    "unisoc": ("UNISOC support", "https://www.unisoc.com/en_us/support"),
    "tensor": ("Google USB driver", "https://developer.android.com/studio/run/win-usb"),
    "exynos": ("Samsung Android USB driver", "https://developer.samsung.com/android-usb-driver"),
}


def firmware_sources(manufacturer: str, chipset: str = "") -> list[tuple[str, str]]:
    normalized_manufacturer = normalize_manufacturer(manufacturer).lower()
    sources = list(VENDOR_RESOURCES.get(normalized_manufacturer, {}).get("firmware", ()))
    if not sources:
        sources.append(("Android device support", "https://www.android.com/"))
    return sources


def driver_sources(manufacturer: str, chipset: str = "") -> list[tuple[str, str]]:
    normalized_manufacturer = normalize_manufacturer(manufacturer).lower()
    sources = list(VENDOR_RESOURCES.get(normalized_manufacturer, {}).get("drivers", ()))
    normalized_chipset = chipset.lower()
    for family, resource in PROCESSOR_RESOURCES.items():
        is_mtk_model_number = family == "mediatek" and re.match(
            r"^mtk?\s*-?\d{4,6}\b",
            normalized_chipset,
        )
        if (family in normalized_chipset or is_mtk_model_number) and resource not in sources:
            sources.append(resource)
    if not sources:
        sources.append(("Android USB driver guidance", "https://developer.android.com/studio/run/win-usb"))
    return sources
