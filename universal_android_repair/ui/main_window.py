from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from universal_android_repair.core.detection import DeviceDetection, DeviceDetectionEngine
from universal_android_repair.core.device_connection import AndroidDeviceConnector, DeviceConnectionError
from universal_android_repair.core.device_profiles import DeviceProfile
from universal_android_repair.core.firmware import FirmwareManager
from universal_android_repair.core.flashing import build_custom_rom_plan, build_stock_rom_plan
from universal_android_repair.core.resource_catalog import driver_sources, firmware_sources


class RepairManagerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Universal Android Repair & ROM Manager")
        self.resize(1080, 760)

        self.detection_engine = DeviceDetectionEngine()
        self.device_connector = AndroidDeviceConnector()
        self.firmware_manager = FirmwareManager()
        self.device: DeviceDetection | None = None
        self.last_connection_message = ""

        self.device_selection = QComboBox()
        self.device_selection.addItem("Auto-detect connected device", None)
        for profile in self.detection_engine.profiles:
            self.device_selection.addItem(f"{profile.manufacturer} {profile.model}", profile)

        self.processor_selection = QComboBox()
        self.processor_selection.addItem("Auto-detect processor", "")
        processors = sorted({profile.chipset for profile in self.detection_engine.profiles})
        for processor in processors:
            self.processor_selection.addItem(processor, processor)

        self.detect_button = QPushButton("Detect / apply selection")
        self.detect_button.clicked.connect(self.detect_device)
        self.scan_button = QPushButton("Check firmware compatibility")
        self.scan_button.clicked.connect(self.check_firmware)
        self.stock_button = QPushButton("Show stock ROM steps")
        self.stock_button.clicked.connect(self.install_stock_rom)
        self.custom_button = QPushButton("Show custom ROM steps")
        self.custom_button.clicked.connect(self.install_custom_rom)

        self.firmware_source = QComboBox()
        self.driver_source = QComboBox()
        self.open_firmware_button = QPushButton("Open firmware site")
        self.open_firmware_button.clicked.connect(lambda: self._open_selected_site(self.firmware_source))
        self.open_driver_button = QPushButton("Open driver site")
        self.open_driver_button.clicked.connect(lambda: self._open_selected_site(self.driver_source))

        self.status_label = QLabel("Connect a device or choose a profile")
        self.device_summary = QTextEdit()
        self.device_summary.setReadOnly(True)
        self.compatibility_list = QListWidget()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self._build_ui()
        self.detect_device()

        self.detection_timer = QTimer(self)
        self.detection_timer.setInterval(5000)
        self.detection_timer.timeout.connect(self._poll_connected_device)
        self.detection_timer.start()

    def _build_ui(self) -> None:
        selection_layout = QFormLayout()
        selection_layout.addRow("Device model:", self.device_selection)
        selection_layout.addRow("Processor / chipset:", self.processor_selection)
        selection_layout.addRow(self.detect_button)
        selection_layout.addRow("Connection status:", self.status_label)

        sources_layout = QFormLayout()
        firmware_row = QHBoxLayout()
        firmware_row.addWidget(self.firmware_source)
        firmware_row.addWidget(self.open_firmware_button)
        driver_row = QHBoxLayout()
        driver_row.addWidget(self.driver_source)
        driver_row.addWidget(self.open_driver_button)
        sources_layout.addRow("Firmware sources:", firmware_row)
        sources_layout.addRow("Driver sources:", driver_row)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.scan_button)
        action_layout.addWidget(self.stock_button)
        action_layout.addWidget(self.custom_button)

        left_column = QVBoxLayout()
        left_column.addLayout(selection_layout)
        left_column.addLayout(sources_layout)
        left_column.addWidget(QLabel("Connected device details:"))
        left_column.addWidget(self.device_summary)
        left_column.addLayout(action_layout)

        compatibility = QVBoxLayout()
        compatibility.addWidget(QLabel("Compatible firmware packages:"))
        compatibility.addWidget(self.compatibility_list)

        log_column = QVBoxLayout()
        log_column.addWidget(QLabel("Operational log:"))
        log_column.addWidget(self.log_output)

        root = QWidget()
        main_layout = QHBoxLayout(root)
        main_layout.addLayout(left_column, 2)
        main_layout.addLayout(compatibility, 1)
        main_layout.addLayout(log_column, 1)
        self.setCentralWidget(root)

    def detect_device(self) -> None:
        selected_profile = self.device_selection.currentData()
        if isinstance(selected_profile, DeviceProfile):
            raw = {
                "adb": {
                    "manufacturer": selected_profile.manufacturer,
                    "model": selected_profile.model,
                    "codename": selected_profile.codename,
                    "chipset": selected_profile.chipset,
                    "platform": selected_profile.platform,
                }
            }
            self.device = self.detection_engine.detect(raw)
            connection_message = "Using manually selected device profile."
        else:
            try:
                result = self.device_connector.detect()
            except DeviceConnectionError as error:
                self._set_connection_error(str(error))
                return
            self.device = self.detection_engine.detect(result.raw) if result.raw else None
            connection_message = result.message

        if self.device:
            chosen_processor = self.processor_selection.currentData()
            if chosen_processor:
                self.device.chipset = chosen_processor
                matching_profile = next(
                    (profile for profile in self.detection_engine.profiles if profile.chipset == chosen_processor),
                    None,
                )
                if matching_profile:
                    self.device.platform = matching_profile.platform
                    if self.device.profile is None:
                        self.device.profile = matching_profile
            self._show_device(self.device)
        else:
            self.status_label.setText("No device detected")
            self.device_summary.setPlainText(
                "Connect a device with USB debugging enabled or in Fastboot mode. "
                "If it is not recognized, install the manufacturer's USB driver."
            )
            self.compatibility_list.clear()

        self._refresh_resource_choices()
        self._log_connection_message(connection_message)

    def _poll_connected_device(self) -> None:
        if self.device_selection.currentData() is None:
            self.detect_device()

    def _show_device(self, device: DeviceDetection) -> None:
        self.status_label.setText(
            self.detection_engine.compatibility_summary(device)
            if device.profile
            else "Device detected; manual profile verification required."
        )
        self.device_summary.setPlainText(
            "\n".join(
                [
                    f"Manufacturer: {device.manufacturer}",
                    f"Model: {device.model}",
                    f"Codename: {device.codename}",
                    f"Chipset: {device.chipset}",
                    f"Platform: {device.platform}",
                    f"CPU architecture: {device.cpu_architecture}",
                    f"Android version: {device.android_version}",
                    f"Bootloader state: {device.bootloader_state}",
                    f"Fastboot available: {'Yes' if device.fastboot_available else 'No'}",
                    f"ADB authorized: {'Yes' if device.adb_authorized else 'No'}",
                    f"Serial: {device.serial_number}",
                    f"Identification: {', '.join(device.identification_sources)}",
                    f"Profile: {device.profile.model if device.profile else 'Not matched'}",
                ]
            )
        )

    def _set_connection_error(self, message: str) -> None:
        self.device = None
        self.status_label.setText("Device detection unavailable")
        self.device_summary.setPlainText(message)
        self.compatibility_list.clear()
        self._refresh_resource_choices()
        self._log_connection_message(message)

    def _log_connection_message(self, message: str) -> None:
        if message and message != self.last_connection_message:
            self.log_output.append(message)
            self.last_connection_message = message

    def _refresh_resource_choices(self) -> None:
        profile = self.device.profile if self.device else self.device_selection.currentData()
        manufacturer = profile.manufacturer if isinstance(profile, DeviceProfile) else ""
        chipset = self.device.chipset if self.device else (
            profile.chipset if isinstance(profile, DeviceProfile) else self.processor_selection.currentData()
        )
        self._populate_sources(self.firmware_source, firmware_sources(manufacturer, chipset or ""))
        self._populate_sources(self.driver_source, driver_sources(manufacturer, chipset or ""))

    @staticmethod
    def _populate_sources(combo: QComboBox, sources: list[tuple[str, str]]) -> None:
        combo.clear()
        for label, url in sources:
            combo.addItem(label, url)

    def _open_selected_site(self, combo: QComboBox) -> None:
        url = combo.currentData()
        if not url or not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "Unable to open website", "The selected website could not be opened.")

    def check_firmware(self) -> None:
        if not self.device:
            QMessageBox.information(self, "No device selected", "Connect a device or select a device profile first.")
            return
        matches = self.firmware_manager.find_package_for_device(self.device)
        self.compatibility_list.clear()
        if not matches:
            self.compatibility_list.addItem("No compatible firmware packages found")
            return

        for package in matches:
            report = self.firmware_manager.verify_compatibility(self.device, package)
            item = QListWidgetItem(f"{package.name} [{report.status.value}]")
            item.setToolTip("\n".join(report.messages))
            self.compatibility_list.addItem(item)
            self.log_output.append(f"{package.name}: {report.status.value} - {', '.join(report.messages)}")

    def install_stock_rom(self) -> None:
        if not self.device:
            QMessageBox.information(self, "No device selected", "Connect a device or select a device profile first.")
            return
        firmware = next(
            (package for package in self.firmware_manager.find_package_for_device(self.device)
             if package.package_type == "factory-image"),
            None,
        )
        if firmware is None:
            QMessageBox.information(self, "No stock firmware", "No matching stock firmware package is in the manifest.")
            return
        plan = build_stock_rom_plan(self.device, firmware)
        self._show_plan(plan.title, plan.warnings, plan.procedures)
        if plan.requires_confirmation:
            QMessageBox.information(
                self,
                "Confirmation required",
                "This is a preparation checklist only. Verify the firmware and back up data before using the vendor's installation workflow.",
            )

    def install_custom_rom(self) -> None:
        if not self.device:
            QMessageBox.information(self, "No device selected", "Connect a device or select a device profile first.")
            return
        rom = next(
            (package for package in self.firmware_manager.find_package_for_device(self.device)
             if package.package_type == "custom-rom"),
            None,
        )
        if rom is None:
            QMessageBox.information(self, "No custom ROM", "No matching custom ROM package is in the manifest.")
            return
        plan = build_custom_rom_plan(self.device, rom)
        self._show_plan(plan.title, plan.warnings, plan.procedures)
        if plan.requires_confirmation:
            QMessageBox.information(
                self,
                "Confirmation required",
                "This is a preparation checklist only. Custom ROM installation can erase user data and requires explicit approval.",
            )

    def _show_plan(self, title: str, warnings: list[str], procedures: list[str]) -> None:
        self.log_output.append(title)
        for warning in warnings:
            self.log_output.append(f"WARNING: {warning}")
        for step in procedures:
            self.log_output.append(f"STEP: {step}")


def create_app() -> QApplication:
    app = QApplication([])
    window = RepairManagerWindow()
    window.show()
    return app
