from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlashingWorkflow:
    title: str
    warnings: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    safe_to_proceed: bool = False


def build_stock_rom_plan(device: Any, firmware: Any) -> FlashingWorkflow:
    warnings = [
        "Factory reset and data loss risk: back up user data before continuing.",
        "Verify the device model, firmware package, and bootloader state again before flashing.",
    ]
    procedures = [
        "Validate device identity and firmware hashes.",
        "Confirm ADB/Fastboot authorization state and required drivers are installed.",
        "Flash only compatible partitions using the official vendor workflow.",
        "Verify the device after installation and report any post-flash issues.",
    ]
    return FlashingWorkflow(
        title=f"Stock ROM install for {device.model}",
        warnings=warnings,
        procedures=procedures,
        requires_confirmation=True,
        safe_to_proceed=True,
    )


def build_custom_rom_plan(device: Any, rom: Any) -> FlashingWorkflow:
    warnings = [
        "Custom ROM installation may erase userdata and require unlocking the bootloader.",
        "Only install a ROM supported by the exact model and codename.",
        "Verify the ROM's checksums and installation instructions before flashing.",
    ]
    procedures = [
        "Check whether the device codename and build baseline are officially supported.",
        "Validate recovery, bootloader, and rollback requirements.",
        "Use the ROM project's documented installation procedure.",
        "Perform a first-boot verification and capture any recovery steps.",
    ]
    return FlashingWorkflow(
        title=f"Custom ROM install for {device.model}",
        warnings=warnings,
        procedures=procedures,
        requires_confirmation=True,
        safe_to_proceed=device.bootloader_state.lower() != "locked",
    )
