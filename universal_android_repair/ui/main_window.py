from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from universal_android_repair.core.detection import DeviceDetection, DeviceDetectionEngine, infer_platform
from universal_android_repair.core.device_connection import AndroidDeviceConnector, DeviceConnectionError
from universal_android_repair.core.device_profiles import DeviceProfile
from universal_android_repair.core.firmware import FirmwareManager
from universal_android_repair.core.flashing import (
    flash_google_stock_ota,
    flash_lineageos_images,
    sideload_lineageos_package,
)
from universal_android_repair.core.official_downloads import download_official_package
from universal_android_repair.core.resource_catalog import driver_sources, firmware_sources
from universal_android_repair.core.windows_driver import install_google_usb_driver


_main_window: RepairManagerWindow | None = None


@dataclass(frozen=True)
class ManufacturerSelection:
    manufacturer: str


class OperationWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation

    def run(self) -> None:
        try:
            self.completed.emit(self.operation())
        except (RuntimeError, OSError) as error:
            self.failed.emit(str(error))


class RepairManagerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Universal Android Repair & ROM Manager")
        self.resize(1280, 840)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(
            """
            QMainWindow, QWidget#appRoot {
                background: #0b1120;
                color: #e2e8f0;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QLabel {
                color: #cbd5e1;
            }
            QFrame#hero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #172554, stop:0.55 #4338ca, stop:1 #7c3aed);
                border: none;
                border-radius: 20px;
            }
            QLabel#heroTitle {
                color: white;
                font-size: 23pt;
                font-weight: 700;
            }
            QLabel#heroSubtitle {
                color: #dbeafe;
                font-size: 10pt;
            }
            QLabel#heroTag {
                color: #ede9fe;
                background: rgba(255, 255, 255, 28);
                border: 1px solid rgba(255, 255, 255, 55);
                border-radius: 12px;
                padding: 8px 13px;
                font-size: 9pt;
                font-weight: 700;
            }
            QFrame[class="sectionCard"] {
                background: #151f32;
                border: 1px solid #29364b;
                border-radius: 16px;
            }
            QLabel[class="sectionTitle"] {
                color: #f1f5f9;
                font-size: 13pt;
                font-weight: 700;
            }
            QLabel[class="sectionSubtitle"] {
                color: #94a3b8;
                font-size: 9pt;
            }
            QLabel#connectionBadge {
                background: #12352f;
                color: #6ee7b7;
                border: 1px solid #17634e;
                border-radius: 10px;
                padding: 7px 10px;
                font-weight: 600;
            }
            QComboBox, QTextEdit, QListWidget, QLineEdit {
                background: #0d1627;
                color: #f1f5f9;
                border: 1px solid #344258;
                border-radius: 9px;
                padding: 8px 10px;
                selection-background-color: #4f46e5;
                selection-color: #ffffff;
            }
            QComboBox:focus, QTextEdit:focus, QListWidget:focus, QLineEdit:focus {
                border: 1px solid #818cf8;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox QAbstractItemView {
                background: #111b2d;
                color: #f1f5f9;
                selection-background-color: #3730a3;
                selection-color: #ffffff;
                border: 1px solid #344258;
                outline: 0;
            }
            QDialog, QMessageBox {
                background: #151f32;
                color: #e2e8f0;
            }
            QPushButton {
                background: #202c42;
                color: #c7d2fe;
                border: 1px solid #3b4b66;
                border-radius: 9px;
                padding: 10px 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #293957;
                border-color: #818cf8;
            }
            QPushButton:pressed {
                background: #3730a3;
            }
            QPushButton:disabled {
                background: #1b2638;
                color: #64748b;
                border-color: #29364b;
            }
            QPushButton#primaryButton {
                background: #4f46e5;
                color: white;
                border: 1px solid #4f46e5;
            }
            QPushButton#primaryButton:hover {
                background: #4338ca;
                border-color: #4338ca;
            }
            QPushButton#successButton {
                background: #059669;
                color: white;
                border: 1px solid #059669;
            }
            QPushButton#successButton:hover {
                background: #047857;
                border-color: #047857;
            }
            QPushButton#warningButton {
                background: #3a2918;
                color: #fdba74;
                border: 1px solid #70451f;
            }
            QPushButton#warningButton:hover {
                background: #52371c;
                border-color: #fb923c;
            }
            QScrollBar:vertical {
                background: #0b1120;
                width: 10px;
                margin: 3px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 5px;
                min-height: 28px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )

        self.detection_engine = DeviceDetectionEngine()
        self.device_connector = AndroidDeviceConnector()
        self.firmware_manager = FirmwareManager()
        self.device: DeviceDetection | None = None
        self.last_connection_message = ""
        self.operation_worker: OperationWorker | None = None
        self.pending_operation: Callable[[], None] | None = None
        self.operation_success: Callable[[object], None] | None = None

        self.device_selection = QComboBox()
        self.device_selection.addItem("Auto-detect connected device", None)
        for profile in self.detection_engine.profiles:
            self.device_selection.addItem(f"{profile.manufacturer} {profile.model}", profile)
        for manufacturer in ("TECNO", "vivo", "Infinix", "OPPO"):
            self.device_selection.addItem(
                f"{manufacturer} (brand only; model unverified)",
                ManufacturerSelection(manufacturer),
            )

        self.processor_selection = QComboBox()
        self.processor_selection.addItem("Auto-detect processor", "")
        processors = sorted({profile.chipset for profile in self.detection_engine.profiles})
        processors.append("MediaTek (unknown SoC)")
        for processor in processors:
            self.processor_selection.addItem(processor, processor)

        self.detect_button = QPushButton("Detect / apply selection")
        self.detect_button.clicked.connect(self.detect_device)
        self.scan_button = QPushButton("Check firmware compatibility")
        self.scan_button.clicked.connect(self.check_firmware)
        self.stock_button = QPushButton("Install stock Pixel OTA")
        self.stock_button.clicked.connect(self.install_stock_rom)
        self.custom_button = QPushButton("Install LineageOS on unlocked Pixel")
        self.custom_button.clicked.connect(self.install_custom_rom)
        self.stock_restore_help_button = QPushButton("Official stock-restore help")
        self.stock_restore_help_button.clicked.connect(self.show_stock_restore_help)

        self.firmware_source = QComboBox()
        self.driver_source = QComboBox()
        self.download_firmware_button = QPushButton("Download verified firmware/image")
        self.download_firmware_button.clicked.connect(self.download_firmware)
        self.open_firmware_button = QPushButton("Open firmware site")
        self.open_firmware_button.clicked.connect(lambda: self._open_selected_site(self.firmware_source))
        self.install_driver_button = QPushButton("Install Google USB driver")
        self.install_driver_button.clicked.connect(self.install_driver)
        self.open_driver_button = QPushButton("Open driver site")
        self.open_driver_button.clicked.connect(lambda: self._open_selected_site(self.driver_source))

        self.status_label = QLabel("Connect a device or choose a profile")
        self.status_label.setObjectName("connectionBadge")
        self.device_summary = QTextEdit()
        self.device_summary.setReadOnly(True)
        self.device_summary.setMinimumHeight(130)
        self.device_summary.setMaximumHeight(155)
        self.compatibility_list = QListWidget()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)

        self._build_ui()
        self.detect_device()

        self.detection_timer = QTimer(self)
        self.detection_timer.setInterval(5000)
        self.detection_timer.timeout.connect(self._poll_connected_device)
        self.detection_timer.start()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(26, 22, 26, 22)
        main_layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_copy = QVBoxLayout()
        title = QLabel("Universal Android Repair")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Device diagnostics, verified firmware, and safer recovery workflows")
        subtitle.setObjectName("heroSubtitle")
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_tag = QLabel("ANDROID DEVICE TOOLKIT")
        hero_tag.setObjectName("heroTag")
        hero_layout.addLayout(hero_copy)
        hero_layout.addStretch(1)
        hero_layout.addWidget(hero_tag, 0, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(hero)

        top_row = QGridLayout()
        top_row.setHorizontalSpacing(16)
        top_row.setVerticalSpacing(16)
        device_card, device_layout = self._section_card(
            "Device setup",
            "Choose a profile or inspect a connected phone.",
        )
        selection_layout = QFormLayout()
        selection_layout.setHorizontalSpacing(14)
        selection_layout.setVerticalSpacing(10)
        selection_layout.addRow("Device model", self.device_selection)
        selection_layout.addRow("Processor / chipset", self.processor_selection)
        device_layout.addLayout(selection_layout)
        device_layout.addWidget(self.detect_button)
        device_layout.addWidget(self.status_label)
        device_layout.addWidget(QLabel("Device details"))
        device_layout.addWidget(self.device_summary)

        resources_card, resources_layout = self._section_card(
            "Firmware & drivers",
            "Check exact model and region; third-party firmware references are labeled.",
        )
        resources_layout.addWidget(QLabel("Firmware source"))
        firmware_row = QHBoxLayout()
        firmware_row.addWidget(self.firmware_source, 1)
        firmware_row.addWidget(self.open_firmware_button)
        resources_layout.addLayout(firmware_row)
        resources_layout.addWidget(self.download_firmware_button)
        resources_layout.addSpacing(8)
        resources_layout.addWidget(QLabel("Driver source"))
        driver_row = QHBoxLayout()
        driver_row.addWidget(self.driver_source, 1)
        driver_row.addWidget(self.open_driver_button)
        resources_layout.addLayout(driver_row)
        resources_layout.addWidget(self.install_driver_button)
        resources_layout.addStretch(1)

        top_row.addWidget(device_card, 0, 0)
        top_row.addWidget(resources_card, 0, 1)
        top_row.setColumnStretch(0, 7)
        top_row.setColumnStretch(1, 5)
        main_layout.addLayout(top_row, 5)

        actions_card, actions_layout = self._section_card(
            "Repair actions",
            "Confirm the target device and review warnings before any operation.",
        )
        action_row = QGridLayout()
        action_row.setHorizontalSpacing(12)
        action_row.setVerticalSpacing(10)
        self.scan_button.setObjectName("primaryButton")
        self.stock_button.setObjectName("successButton")
        self.custom_button.setObjectName("warningButton")
        action_row.addWidget(self.scan_button, 0, 0)
        action_row.addWidget(self.stock_button, 0, 1)
        action_row.addWidget(self.custom_button, 1, 0)
        action_row.addWidget(self.stock_restore_help_button, 1, 1)
        action_row.setColumnStretch(0, 1)
        action_row.setColumnStretch(1, 1)
        actions_layout.addLayout(action_row)
        main_layout.addWidget(actions_card)

        bottom_row = QGridLayout()
        bottom_row.setHorizontalSpacing(16)
        compatibility_card, compatibility_layout = self._section_card(
            "Compatibility",
            "Packages are matched to the detected device profile.",
        )
        compatibility_layout.addWidget(self.compatibility_list)
        log_card, log_layout = self._section_card(
            "Activity log",
            "Device detection and operation status.",
        )
        log_layout.addWidget(self.log_output)
        bottom_row.addWidget(compatibility_card, 1, 0)
        bottom_row.addWidget(log_card, 1, 1)
        bottom_row.setColumnStretch(0, 1)
        bottom_row.setColumnStretch(1, 1)
        main_layout.addLayout(bottom_row, 3)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(root)
        self.setCentralWidget(scroll_area)

    @staticmethod
    def _section_card(title_text: str, subtitle_text: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        title = QLabel(title_text)
        title.setProperty("class", "sectionTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return card, layout

    def detect_device(self) -> None:
        selected_profile = self.device_selection.currentData()
        if isinstance(selected_profile, ManufacturerSelection):
            raw = {
                "adb": {
                    "manufacturer": selected_profile.manufacturer,
                    "model": "Not detected",
                    "chipset": "Not detected",
                }
            }
            self.device = self.detection_engine.detect(raw)
            connection_message = f"Using {selected_profile.manufacturer} brand selection; exact model is unverified."
        elif isinstance(selected_profile, DeviceProfile):
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
                self.device.platform = infer_platform(
                    chosen_processor,
                    matching_profile.platform if matching_profile else self.device.platform,
                )
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
        manufacturer = (
            self.device.manufacturer
            if self.device and self.device.manufacturer != "Not detected"
            else profile.manufacturer
            if isinstance(profile, (DeviceProfile, ManufacturerSelection))
            else ""
        )
        chipset = self.device.chipset if self.device else (
            profile.chipset
            if isinstance(profile, DeviceProfile)
            else self.processor_selection.currentData()
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
        if not self._has_supported_pixel():
            return
        package_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select the official Google full OTA package",
            "",
            "Android OTA packages (*.zip)",
        )
        if not package_path:
            return
        if QMessageBox.question(
            self,
            "Confirm stock OTA sideload",
            "This will sideload the selected Google OTA package to the connected Pixel. "
            "The package's device metadata and SHA-256 record are checked first; download it "
            "through this app and keep its .sha256 file beside it. Back up important data and "
            "put the device in Recovery > Apply update > Apply from ADB. If recovery is not "
            "detected automatically, select the Pixel profile manually first. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        device = self.device
        self._start_operation(
            "Sideloading Google stock OTA",
            lambda: flash_google_stock_ota(device, package_path),
            lambda _: self.log_output.append("Google stock OTA sideload completed."),
        )

    def show_stock_restore_help(self) -> None:
        selected = self.device_selection.currentData()
        manufacturer = (
            self.device.manufacturer
            if self.device and self.device.manufacturer != "Not detected"
            else selected.manufacturer
            if isinstance(selected, (DeviceProfile, ManufacturerSelection))
            else ""
        )
        model = self.device.model if self.device else (
            selected.model if isinstance(selected, DeviceProfile) else "Unspecified model"
        )
        if not manufacturer:
            QMessageBox.information(
                self,
                "Select a device first",
                "Connect a phone or choose its manufacturer/model to open the matching official recovery support.",
            )
            return

        sources = firmware_sources(manufacturer)
        source_label, source_url = sources[0]
        if manufacturer.strip().lower() == "tecno":
            message = (
                f"Device: {model}\n\n"
                "TECNO/Carlcare provides official software-upgrade and authorized repair support. "
                "A public, authorized stock-firmware flashing procedure for this exact model has "
                "not been validated in this app. If the phone is not booting, use authorized "
                "TECNO/Carlcare service rather than generic MediaTek BROM/Preloader tools.\n\n"
                "This app will not bypass secure-boot/authentication checks or run generic "
                "MediaTek flashing commands."
            )
        else:
            message = (
                f"Device: {model}\n\n"
                f"Open {manufacturer}'s official support resources for this model. Recovery and "
                "factory-image procedures vary by exact model and region. No generic flashing "
                "command will be run for an unverified device."
            )
        QMessageBox.information(self, "Official stock-restore support", message)
        if not QDesktopServices.openUrl(QUrl(source_url)):
            QMessageBox.warning(
                self,
                "Unable to open support page",
                f"The selected official support page could not be opened: {source_label}.",
            )

    def install_custom_rom(self) -> None:
        if not self._has_supported_pixel():
            return
        if self.device.bootloader_state.lower() != "unlocked" or not self.device.fastboot_available:
            QMessageBox.warning(
                self,
                "Unlocked Fastboot device required",
                "LineageOS installation is enabled only for a supported Pixel already in Fastboot "
                "with its bootloader unlocked. This application will not unlock it.",
            )
            return
        image_directory = QFileDialog.getExistingDirectory(
            self,
            "Select the folder containing LineageOS images",
        )
        if not image_directory:
            return
        package_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select the official LineageOS package",
            image_directory,
            "LineageOS packages (*.zip)",
        )
        if not package_path:
            return
        if QMessageBox.question(
            self,
            "Erase and flash LineageOS",
            f"This will flash boot, dtbo, vendor_kernel_boot, and vendor_boot on "
            f"{self.device.model} ({self.device.codename}), then sideload the selected package. "
            "The official guide's required stock-firmware baseline must be met. It also requires "
            "a factory reset, which you must perform manually in "
            "Recovery; all user data can be erased. All selected images and the package must be "
            "downloaded and checksum-verified through this app, and from the same LineageOS build. "
            "Verify the stock-firmware baseline and back up data. "
            "No bootloader unlocking or account/FRP bypass will be performed. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        device = self.device

        def flash_images() -> str:
            flash_lineageos_images(device, image_directory, package_path)
            return package_path

        def images_flashed(path: object) -> None:
            self.log_output.append(
                "LineageOS images flashed. Boot to Lineage Recovery, perform the required factory "
                "reset, select Apply update > Apply from ADB, then confirm below to sideload."
            )
            if QMessageBox.question(
                self,
                "Ready to sideload?",
                "Only continue after the connected device shows Recovery's 'Apply from ADB' screen. "
                "The package's device metadata will be checked before sideloading.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self.pending_operation = lambda: self._start_operation(
                    "Sideloading LineageOS",
                    lambda: sideload_lineageos_package(device, str(path)),
                    lambda _: self.log_output.append("LineageOS sideload completed."),
                )

        self._start_operation("Flashing LineageOS images", flash_images, images_flashed)

    def download_firmware(self) -> None:
        if not self._has_supported_pixel():
            return
        url, accepted = QInputDialog.getText(
            self,
            "Official firmware URL",
            "Paste a direct HTTPS Google or LineageOS download URL:",
        )
        if not accepted or not url.strip():
            return
        checksum, accepted = QInputDialog.getText(
            self,
            "Published checksum",
            "Enter the package's published SHA-256 checksum:",
        )
        if not accepted or not checksum.strip():
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save verified firmware or image",
            "",
            "Firmware packages and images (*.zip *.img);;All files (*)",
        )
        if not destination:
            return
        self._start_operation(
            "Downloading and verifying firmware",
            lambda: download_official_package(url.strip(), destination, checksum.strip()),
            lambda path: self.log_output.append(f"Verified firmware saved to {path}"),
        )

    def install_driver(self) -> None:
        if QMessageBox.question(
            self,
            "Install Google USB driver",
            "Download the Google USB driver from Google's official HTTPS repository and start "
            "Windows' signed driver installer. Windows will request administrator approval. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._start_operation(
            "Installing Google USB driver",
            install_google_usb_driver,
            lambda path: self.log_output.append(f"Google USB driver installed from {path}."),
        )

    def _has_supported_pixel(self) -> bool:
        if not self.device:
            QMessageBox.information(self, "No device selected", "Connect a device or select a device profile first.")
            return False
        if (
            self.device.manufacturer.lower() != "google"
            or self.device.codename.lower() not in {"shiba", "tokay"}
        ):
            QMessageBox.warning(
                self,
                "Unsupported device",
                "Automated firmware operations currently support only Google Pixel 8 (shiba) and "
                "Pixel 9 (tokay).",
            )
            return False
        return True

    def _start_operation(
        self,
        title: str,
        operation: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        if self.operation_worker and self.operation_worker.isRunning():
            QMessageBox.information(self, "Operation in progress", "Wait for the current operation to finish.")
            return
        self.log_output.append(f"{title}...")
        worker = OperationWorker(operation)
        self.operation_success = on_success
        worker.completed.connect(self._operation_completed)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(self._operation_finished)
        self.operation_worker = worker
        worker.start()

    def _operation_completed(self, result: object) -> None:
        if self.operation_success:
            self.operation_success(result)

    def _operation_failed(self, message: str) -> None:
        self.operation_success = None
        QMessageBox.critical(self, "Operation failed", message)

    def _operation_finished(self) -> None:
        self.operation_worker = None
        self.operation_success = None
        if self.pending_operation:
            operation = self.pending_operation
            self.pending_operation = None
            operation()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.operation_worker and self.operation_worker.isRunning():
            QMessageBox.information(
                self,
                "Operation in progress",
                "Wait for the current firmware or driver operation to finish before closing.",
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _show_plan(self, title: str, warnings: list[str], procedures: list[str]) -> None:
        self.log_output.append(title)
        for warning in warnings:
            self.log_output.append(f"WARNING: {warning}")
        for step in procedures:
            self.log_output.append(f"STEP: {step}")


def create_app() -> QApplication:
    global _main_window
    app = QApplication([])
    _main_window = RepairManagerWindow()
    _main_window.show()
    return app
