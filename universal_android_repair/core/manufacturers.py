from __future__ import annotations


MANUFACTURER_ALIASES = {
    "tecno": "TECNO",
    "tecno mobile": "TECNO",
    "tecno mobile limited": "TECNO",
    "vivo": "vivo",
    "vivo mobile communication": "vivo",
    "vivo mobile communication co., ltd.": "vivo",
    "infinix": "Infinix",
    "infinix mobility": "Infinix",
    "infinix mobility limited": "Infinix",
    "oppo": "OPPO",
    "oppo mobile": "OPPO",
    "oppo mobile telecommunications corp.": "OPPO",
    "guangdong oppo mobile telecommunications corp., ltd.": "OPPO",
}


def normalize_manufacturer(manufacturer: str) -> str:
    normalized = manufacturer.strip().lower()
    return MANUFACTURER_ALIASES.get(normalized, manufacturer.strip())
