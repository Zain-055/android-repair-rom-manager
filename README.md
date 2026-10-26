# Universal Android Repair & ROM Manager

This project provides a desktop application skeleton for Android device diagnosis, firmware validation, and ROM installation workflows.

## Features

- Device detection using ADB/Fastboot and USB metadata
- Automatic ADB/Fastboot polling after connecting a phone, with manual model and chipset selection
- One-click access to official manufacturer firmware and USB/processor support pages
- Device profile matching for supported platforms
- Firmware compatibility checks and manifest-based verification
- Stock ROM and custom ROM installation workflow planning
- SQLite-backed history and metadata storage
- PySide6 desktop interface

## Run locally

```bash
python -m pip install -r requirements.txt
python -m universal_android_repair.app
```

## Build the Windows executable

Use 64-bit Python 3.11 or newer on Windows:

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller --clean --noconfirm UniversalAndroidRepair.spec
```

The standalone executable is written to `dist\UniversalAndroidRepair.exe`. The app stores its database under `%LOCALAPPDATA%\UniversalAndroidRepair\repair_manager.db`, so application data persists between launches. The installer-free executable does not bundle Android Platform Tools or device USB drivers; install them separately and make `adb`/`fastboot` available on `PATH`.

## Test

```bash
python -m pytest -q
```

## Safety

The project intentionally models safe firmware practices: it validates device and firmware identity before flashing, blocks unsupported packages, and requires explicit confirmation for operations that risk data loss or bootloader changes.

## Device and firmware sources

Automatic identification requires Android Platform Tools (`adb` and `fastboot`) to be installed and available on `PATH`. ADB identification requires USB debugging to be enabled and authorized on the device; Fastboot identification works while the device is in Fastboot mode. Install the appropriate manufacturer's USB driver if the device is not listed.

The source selectors open official manufacturer or processor-vendor support pages in the system browser. This application does not download firmware or drivers, install drivers, or flash a device. Confirm the exact model, region, package integrity, and vendor instructions before using any external package.
