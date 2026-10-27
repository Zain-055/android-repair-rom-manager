from __future__ import annotations

import ctypes
import http.client
import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from ctypes import wintypes

from .official_downloads import DownloadError, official_url_opener, validate_official_url


GOOGLE_USB_DRIVER_URL = "https://dl.google.com/android/repository/usb_driver_r13-windows.zip"


class DriverInstallError(RuntimeError):
    """Raised when the Google USB driver cannot be installed."""


def install_google_usb_driver() -> Path:
    if platform.system() != "Windows":
        raise DriverInstallError("Automatic Google USB driver installation is available on Windows only.")

    validate_official_url(GOOGLE_USB_DRIVER_URL)
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "UniversalAndroidRepair" / "drivers" / "google-usb"
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "usb_driver_r13-windows.zip"
    extracted = root / "usb_driver_r13"
    if not (extracted / "android_winusb.inf").exists():
        temporary_archive = archive_path.with_suffix(".zip.part")
        try:
            request = urllib.request.Request(
                GOOGLE_USB_DRIVER_URL,
                headers={"User-Agent": "UniversalAndroidRepair/1.0"},
            )
            with official_url_opener().open(request, timeout=30) as response:
                validate_official_url(response.geturl())
                with temporary_archive.open("wb") as output:
                    shutil.copyfileobj(response, output)
            temporary_archive.replace(archive_path)
            _extract_driver_archive(archive_path, extracted)
        except (OSError, zipfile.BadZipFile, DownloadError, http.client.HTTPException) as error:
            temporary_archive.unlink(missing_ok=True)
            raise DriverInstallError(f"Could not retrieve the official Google USB driver: {error}") from error

    inf_path = extracted / "android_winusb.inf"
    if not inf_path.is_file() or not any(extracted.glob("*.cat")):
        raise DriverInstallError("The downloaded Google driver package is missing its INF or signature catalog.")
    _run_elevated_pnputil(inf_path)
    return inf_path


def _extract_driver_archive(archive_path: Path, destination: Path) -> None:
    staging = destination.with_name(f"{destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                target = (staging / entry.filename).resolve()
                if not target.is_relative_to(staging.resolve()):
                    raise DriverInstallError("The driver archive contains an unsafe path.")
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        inf_files = list(staging.rglob("android_winusb.inf"))
        if len(inf_files) != 1:
            raise DriverInstallError("The driver archive did not contain exactly one Google USB driver INF.")
        final_source = inf_files[0].parent
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(final_source, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _run_elevated_pnputil(inf_path: Path) -> None:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    executable = system_root / "System32" / "pnputil.exe"
    arguments = subprocess.list2cmdline(["/add-driver", str(inf_path), "/install"])
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.c_void_p),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", ctypes.c_void_p),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", ctypes.c_void_p),
            ("hProcess", wintypes.HANDLE),
        ]

    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    info = ShellExecuteInfo(
        cbSize=ctypes.sizeof(ShellExecuteInfo),
        fMask=0x00000040,
        lpVerb="runas",
        lpFile=str(executable),
        lpParameters=arguments,
        nShow=1,
    )
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:
            raise DriverInstallError("Administrator approval was cancelled.")
        raise DriverInstallError(f"Windows could not start the driver installer: {ctypes.WinError(error)}")
    if not info.hProcess:
        raise DriverInstallError("Windows did not return a handle for the driver installer.")

    try:
        wait_result = kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        if wait_result != 0:
            raise DriverInstallError(f"Waiting for the driver installer failed: {ctypes.WinError(ctypes.get_last_error())}")
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
            raise DriverInstallError(f"Could not read the driver installer result: {ctypes.WinError(ctypes.get_last_error())}")
        if exit_code.value != 0:
            raise DriverInstallError(f"Windows driver installation failed with pnputil exit code {exit_code.value}.")
    finally:
        kernel32.CloseHandle(info.hProcess)
