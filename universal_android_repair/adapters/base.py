from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AdapterSupportProfile:
    manufacturer: str
    platform: str
    chipset_family: str
    supported_communication_protocols: list[str] = field(default_factory=list)
    supported_device_models: list[str] = field(default_factory=list)
    required_drivers: list[str] = field(default_factory=list)
    firmware_formats: list[str] = field(default_factory=list)
    installation_requirements: str = "User confirmation required before modifying partitions."


class DeviceAdapter:
    """Base interface for platform-level support adapters."""

    profile = AdapterSupportProfile(
        manufacturer="Unknown",
        platform="Unknown",
        chipset_family="Unknown",
        supported_communication_protocols=[],
        supported_device_models=[],
        required_drivers=[],
        firmware_formats=[],
    )

    @classmethod
    def detect(cls, device_info: dict) -> bool:
        return False

    @classmethod
    def supported_protocols(cls) -> list[str]:
        return list(cls.profile.supported_communication_protocols)

    @classmethod
    def supported_models(cls) -> list[str]:
        return list(cls.profile.supported_device_models)
