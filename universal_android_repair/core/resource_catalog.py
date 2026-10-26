from __future__ import annotations


VENDOR_RESOURCES: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "google": {
        "firmware": (
            ("Google Pixel factory images", "https://developers.google.com/android/images"),
            ("Google Pixel OTA images", "https://developers.google.com/android/ota"),
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
}

PROCESSOR_RESOURCES: dict[str, tuple[str, str]] = {
    "qualcomm": ("Qualcomm support", "https://www.qualcomm.com/support"),
    "mediatek": ("MediaTek support", "https://www.mediatek.com/support"),
    "unisoc": ("UNISOC support", "https://www.unisoc.com/en_us/support"),
    "tensor": ("Google USB driver", "https://developer.android.com/studio/run/win-usb"),
    "exynos": ("Samsung Android USB driver", "https://developer.samsung.com/android-usb-driver"),
}


def firmware_sources(manufacturer: str, chipset: str = "") -> list[tuple[str, str]]:
    sources = list(VENDOR_RESOURCES.get(manufacturer.strip().lower(), {}).get("firmware", ()))
    if not sources:
        sources.append(("Android device support", "https://www.android.com/"))
    return sources


def driver_sources(manufacturer: str, chipset: str = "") -> list[tuple[str, str]]:
    sources = list(VENDOR_RESOURCES.get(manufacturer.strip().lower(), {}).get("drivers", ()))
    normalized_chipset = chipset.lower()
    for family, resource in PROCESSOR_RESOURCES.items():
        if family in normalized_chipset and resource not in sources:
            sources.append(resource)
    if not sources:
        sources.append(("Android USB driver guidance", "https://developer.android.com/studio/run/win-usb"))
    return sources
