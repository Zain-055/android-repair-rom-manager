# Universal Android Repair & ROM Manager

Universal Android Repair & ROM Manager is a desktop toolkit for ADB/Fastboot diagnostics, device and MediaTek identification, and firmware compatibility checks. It supports checksum-verified Pixel downloads, Google USB driver installation, and guarded Pixel 8/9 stock-OTA and LineageOS workflows. TECNO and Infinix support includes firmware references, not generic MediaTek flashing.

## Features

- Device detection using ADB/Fastboot and USB metadata
- Automatic ADB/Fastboot polling after connecting a phone, with manual model and chipset selection
- Manual brand selection for TECNO, vivo, Infinix, and OPPO when no device is connected
- Official firmware downloads with SHA-256 verification
- Guided access to official manufacturer firmware and USB/processor support pages, plus a clearly labeled third-party firmware catalog for TECNO and Infinix
- Automated Google USB driver download and Windows signed-driver installation
- MediaTek SoC identification and official support links for TECNO, vivo, Infinix, and OPPO
- TECNO Camon 19 Neo (CH6i) profile detection with official stock-restore guidance
- Device profile matching for supported platforms
- Firmware compatibility checks and manifest-based verification
- Google Pixel full-OTA sideloading and guarded LineageOS installation for Pixel 8/9
- SQLite-backed history and metadata storage
- PySide6 desktop interface
- Windows ADB/Fastboot child processes run without opening console windows

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

The standalone executable is written to `dist\UniversalAndroidRepair.exe`. The app stores its database under `%LOCALAPPDATA%\UniversalAndroidRepair\repair_manager.db`, so application data persists between launches. The installer-free executable does not bundle Android Platform Tools; install them separately and make `adb`/`fastboot` available on `PATH`.

## Test

```bash
python -m pytest -q
```

## Safety

Device detection recognizes MediaTek chipset identifiers and common manufacturer names for TECNO, vivo, Infinix, and OPPO. Their official support/service pages are available in the source selectors. TECNO Firmware is also listed as a third-party firmware-finding reference for TECNO and Infinix; it is not an official manufacturer source, and users must independently verify model, region, package integrity, and provenance. TECNO Camon 19 Neo (CH6i) is included as a recognized device profile with official-service restore guidance; no public, authorized device-specific flashing procedure has been validated for it, so no MediaTek BROM/Preloader flashing is performed. A recognized brand or chipset does not imply support for every model: exact model, region, firmware, drivers, and flashing procedures must be validated individually. Automated firmware operations currently support Google Pixel 8 (`shiba`) and Pixel 9 (`tokay`) only. Downloads must use a direct HTTPS Google or LineageOS URL and a SHA-256 checksum published by that vendor. The app records the source and checksum, then rechecks both immediately before installing; Android OTA package device metadata is also checked. Google USB drivers are fetched from Google's official repository; Windows prompts for administrator approval and validates the signed driver package before installation.

Stock firmware is installed by sideloading a Google full OTA from Recovery. LineageOS installation flashes only the documented Pixel partitions and is allowed only when the device is already in Fastboot with its bootloader unlocked. The app does not unlock bootloaders, erase accounts, or bypass screen locks, Factory Reset Protection (FRP), or other account protections. LineageOS requires a manual factory reset in Recovery; back up data and follow the current device-specific LineageOS guide before continuing.

## Device and firmware sources

Automatic identification requires Android Platform Tools (`adb` and `fastboot`) to be installed and available on `PATH`. ADB identification requires USB debugging to be enabled and authorized on the device; Fastboot identification works while the device is in Fastboot mode. Google USB driver installation is available in the app on Windows; use the manufacturer's official instructions for other devices.

The source selectors open official manufacturer or processor-vendor pages in the system browser, and the TECNO/Infinix firmware selector also lists the third-party TECNO Firmware catalog. Downloads from that catalog are opened and managed on the site, not downloaded or verified by this app. To download a package or image in the app, paste its direct official Google or LineageOS URL and the checksum published by that vendor. Keep the generated `.sha256` sidecar next to each file; flashing accepts only files downloaded and verified by the app. For LineageOS, use the same build for all images and the ROM package. Never install a package for a different model or continue if its checksum does not match.
