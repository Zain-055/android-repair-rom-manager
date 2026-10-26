from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field


class DeviceConnectionError(RuntimeError):
    """Raised when Android Platform Tools cannot inspect connected devices."""


@dataclass
class DeviceConnectionResult:
    raw: dict[str, dict[str, object]] = field(default_factory=dict)
    message: str = "No ADB or Fastboot device detected."


class AndroidDeviceConnector:
    """Read device identity through the installed ADB and Fastboot tools."""

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout

    def detect(self) -> DeviceConnectionResult:
        adb_path = shutil.which("adb")
        fastboot_path = shutil.which("fastboot")
        if not adb_path and not fastboot_path:
            raise DeviceConnectionError(
                "Android Platform Tools were not found. Install ADB/Fastboot and add them to PATH."
            )

        raw: dict[str, dict[str, object]] = {}
        messages: list[str] = []

        if adb_path:
            result = self._run([adb_path, "devices", "-l"])
            adb_devices = self._parse_adb_devices(result.stdout)
            if adb_devices:
                serial, state = adb_devices[0]
                adb_data: dict[str, object] = {"serial": serial, "adb_authorized": state == "device"}
                if state == "device":
                    properties = self._read_adb_properties(adb_path, serial)
                    adb_data.update(self._map_adb_properties(properties))
                    messages.append(f"Connected through ADB ({serial}).")
                else:
                    messages.append(f"ADB device {serial} is {state}; authorize USB debugging on the device.")
                raw["adb"] = adb_data
            else:
                messages.append("No ADB device detected.")
        else:
            messages.append("ADB is not installed.")

        if fastboot_path:
            result = self._run([fastboot_path, "devices"])
            fastboot_devices = self._parse_fastboot_devices(result.stdout)
            if fastboot_devices:
                serial = fastboot_devices[0]
                fastboot_data: dict[str, object] = {"serial": serial, "available": True}
                for variable, key in (
                    ("product", "device"),
                    ("unlocked", "bootloader_state"),
                ):
                    value = self._read_fastboot_variable(fastboot_path, serial, variable)
                    if value:
                        fastboot_data[key] = (
                            {"yes": "unlocked", "no": "locked"}.get(value.lower(), value)
                            if key == "bootloader_state"
                            else value
                        )
                raw["fastboot"] = fastboot_data
                messages.append(f"Connected through Fastboot ({serial}).")
            else:
                messages.append("No Fastboot device detected.")
        else:
            messages.append("Fastboot is not installed.")

        if "adb" not in raw and "fastboot" not in raw:
            return DeviceConnectionResult(message=" ".join(messages))
        return DeviceConnectionResult(raw=raw, message=" ".join(messages))

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DeviceConnectionError(f"{command[0]} did not respond within {self.timeout:g} seconds.") from error
        except OSError as error:
            raise DeviceConnectionError(f"Could not start {command[0]}: {error}") from error
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise DeviceConnectionError(detail or f"{command[0]} exited with status {result.returncode}.")
        return result

    @staticmethod
    def _parse_adb_devices(output: str) -> list[tuple[str, str]]:
        devices: list[tuple[str, str]] = []
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] in {"device", "unauthorized", "offline"}:
                devices.append((parts[0], parts[1]))
        return devices

    @staticmethod
    def _parse_fastboot_devices(output: str) -> list[str]:
        return [parts[0] for line in output.splitlines() if (parts := line.strip().split())]

    def _read_adb_properties(self, adb_path: str, serial: str) -> dict[str, str]:
        result = self._run([adb_path, "-s", serial, "shell", "getprop"])
        properties: dict[str, str] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"\[([^\]]+)\]: \[(.*)\]$", line.strip())
            if match and match.group(2):
                properties[match.group(1)] = match.group(2)
        return properties

    def _read_fastboot_variable(self, fastboot_path: str, serial: str, variable: str) -> str:
        try:
            result = subprocess.run(
                [fastboot_path, "-s", serial, "getvar", variable],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DeviceConnectionError(f"Fastboot did not respond while reading {variable}.") from error
        except OSError as error:
            raise DeviceConnectionError(f"Could not query Fastboot variable {variable}: {error}") from error
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        match = re.search(rf"{re.escape(variable)}:\s*(\S+)", output, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    @staticmethod
    def _map_adb_properties(properties: dict[str, str]) -> dict[str, object]:
        manufacturer = properties.get("ro.product.manufacturer") or properties.get("ro.product.vendor.manufacturer")
        model = properties.get("ro.product.model") or properties.get("ro.product.vendor.model")
        codename = properties.get("ro.product.device") or properties.get("ro.build.product")
        chipset = properties.get("ro.soc.model") or properties.get("ro.hardware")
        lock_state = properties.get("ro.boot.flash.locked")
        return {
            "manufacturer": manufacturer,
            "model": model,
            "codename": codename,
            "chipset": chipset,
            "cpu_architecture": properties.get("ro.product.cpu.abi"),
            "android_version": properties.get("ro.build.version.release"),
            "build_fingerprint": properties.get("ro.build.fingerprint"),
            "bootloader_state": {"1": "locked", "0": "unlocked"}.get(lock_state, ""),
        }
