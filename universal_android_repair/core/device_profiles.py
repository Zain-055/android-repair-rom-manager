from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DeviceProfile:
    manufacturer: str
    model: str
    codename: str
    chipset: str
    platform: str
    supported_protocols: list[str] = field(default_factory=list)
    required_drivers: list[str] = field(default_factory=list)
    firmware_formats: list[str] = field(default_factory=list)
    model_aliases: list[str] = field(default_factory=list)
    bootloader_requirements: str = "Unlocked bootloader required for custom ROM installs"
    supported_roms: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "DeviceProfile":
        return cls(
            manufacturer=data.get("manufacturer", "Unknown"),
            model=data.get("model", "Unknown"),
            codename=data.get("codename", "unknown"),
            chipset=data.get("chipset", "Unknown"),
            platform=data.get("platform", "Unknown"),
            supported_protocols=data.get("supported_protocols", []),
            required_drivers=data.get("required_drivers", []),
            firmware_formats=data.get("firmware_formats", []),
            model_aliases=data.get("model_aliases", []),
            bootloader_requirements=data.get("bootloader_requirements", cls.__dataclass_fields__["bootloader_requirements"].default),
            supported_roms=data.get("supported_roms", []),
        )


def load_device_profiles(path: str | Path | None = None) -> list[DeviceProfile]:
    base_dir = Path(__file__).resolve().parents[1]
    profile_path = Path(path) if path else base_dir / "config" / "device_profiles.json"
    with profile_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    profiles = payload.get("profiles", [])
    return [DeviceProfile.from_mapping(item) for item in profiles]


def find_matching_profile(model_name: str, profiles: list[DeviceProfile]) -> DeviceProfile | None:
    if not model_name:
        return None
    normalized = model_name.strip().lower()
    for profile in profiles:
        identifiers = [profile.model, profile.codename, *profile.model_aliases]
        if any(identifier.strip().lower() == normalized for identifier in identifiers):
            return profile
    return None
