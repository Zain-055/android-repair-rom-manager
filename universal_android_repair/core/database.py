from __future__ import annotations

import os
import sqlite3
from pathlib import Path
import sys
from typing import Any


class DatabaseManager:
    """Small SQLite-backed record store for device and operation history."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if getattr(sys, "frozen", False):
            data_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "UniversalAndroidRepair"
            default_path = data_root / "repair_manager.db"
        else:
            base = Path(__file__).resolve().parents[1]
            default_path = base / "data" / "repair_manager.db"
        self.db_path = Path(db_path) if db_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT,
                    model TEXT,
                    codename TEXT,
                    chipset TEXT,
                    platform TEXT,
                    android_version TEXT,
                    firmware_support TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS firmware_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    codename TEXT,
                    chipset TEXT,
                    package_type TEXT,
                    official INTEGER,
                    source TEXT,
                    sha256 TEXT,
                    verification_status TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_model TEXT,
                    firmware_name TEXT,
                    status TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_device_profile(self, **fields: Any) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO device_profiles (
                    manufacturer, model, codename, chipset, platform, android_version, firmware_support
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fields.get("manufacturer"),
                    fields.get("model"),
                    fields.get("codename"),
                    fields.get("chipset"),
                    fields.get("platform"),
                    fields.get("android_version"),
                    fields.get("firmware_support"),
                ),
            )
            conn.commit()

    def save_firmware_package(self, **fields: Any) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO firmware_packages (
                    name, manufacturer, model, codename, chipset, package_type, official, source, sha256, verification_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fields.get("name"),
                    fields.get("manufacturer"),
                    fields.get("model"),
                    fields.get("codename"),
                    fields.get("chipset"),
                    fields.get("package_type"),
                    int(bool(fields.get("official"))),
                    fields.get("source"),
                    fields.get("sha256"),
                    fields.get("verification_status"),
                ),
            )
            conn.commit()

    def log_operation(self, device_model: str, firmware_name: str, status: str, notes: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO operation_history (device_model, firmware_name, status, notes) VALUES (?, ?, ?, ?)",
                (device_model, firmware_name, status, notes),
            )
            conn.commit()

    def fetch_history(self, limit: int = 10) -> list[dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT device_model, firmware_name, status, notes, created_at FROM operation_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
