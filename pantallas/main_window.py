from __future__ import annotations

from functools import partial

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCloseEvent, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .build_info import BUILD_ID
from .models import MonitorInfo, WindowInfo
from .monitor_state import (
    load_disabled_monitors,
    reconcile_active_devices,
    remove_disabled_monitor,
    save_disabled_monitor,
)
from .preferences import (
    load_preferences,
    save_preferences,
    set_windows_startup,
    startup_is_registered,
)
from .rules import RuleEnforcer, RuleStore
from .update_service import UpdateWorker, launch_installer_after_exit
from .windows_api import (
    apply_monitor_layout,
    disable_monitor,
    enable_monitor,
    enum_monitors,
    enum_windows,
    get_monitor_brightness,
    set_monitor_brightness,
)


APP_STYLE = """
QMainWindow, QWidget {
    background: #0d1117;
    color: #e6edf3;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background: #161b22;
    color: #8b949e;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background: #21262d;
    color: #f0f6fc;
}
QFrame#Card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
}
QPushButton {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 7px;
    padding: 7px 12px;
}
QPushButton:hover {
    background: #30363d;
}
QPushButton#PrimaryButton {
    background: #238636;
    border-color: #2ea043;
    color: white;
    font-weight: 600;
}
QPushButton#DangerButton {
    background: #3d171b;
    border-color: #6e3038;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px;
}
QTableWidget {
    background: #0d1117;
    alternate-background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    gridline-color: #21262d;
}
QHeaderView::section {
    background: #161b22;
    color: #8b949e;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 7px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #30363d;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #58a6ff;
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QCheckBox {
    spacing: 7px;
}
"""


class MonitorItem(QGraphicsRectItem):
    def __init__(
        self,
        monitor: MonitorInfo,
        scale: float,
        selected_callback,
        moved_callback,
    ) -> None:
        super().__init__()
        self.monitor = monitor
        self.scale_factor = scale
        self.selected_callback = selected_callback
        self.moved_callback = moved_callback
        self.pending_orientation = monitor.orientation

        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.label = QGraphicsSimpleTextItem(self)
        self.label.setBrush(QColor("#f0f6fc"))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        self.label.setFont(font)
        self.set_selected_visual(False)
        self.update_geometry(monitor.orientation)

    def update_geometry(self, orientation: int) -> None:
        self.pending_orientation = orientation
        width = self.monitor.width
        height = self.monitor.height
        if (self.monitor.orientation // 90) % 2 != (orientation // 90) % 2:
            width, height = height, width
        sw = max(120.0, width * self.scale_factor)
        sh = max(80.0, height * self.scale_factor)
        self.setRect(0, 0, sw, sh)
        primary = " · PRINCIPAL" if self.monitor.primary else ""
        self.label.setText(
            f"{self.monitor.name}{primary}\n"
            f"{width} × {height}\n"
            f"{orientation_label(orientation)}"
        )
        self.label.setPos(12, 10)

    def set_selected_visual(self, selected: bool) -> None:
        color = QColor("#58a6ff") if selected else QColor("#30363d")
        width = 3 if selected else 2
        self.setPen(QPen(color, width))
        self.setBrush(QColor("#1f6feb") if self.monitor.primary else QColor("#21262d"))

    def mousePressEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.selected_callback(self.monitor.device)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
        self.moved_callback(self.monitor.device)


def orientation_label(degrees: int) -> str:
    return {
        0: "Horizontal",
        90: "Vertical",
        180: "Horizontal invertida",
        270: "Vertical invertida",
    }.get(degrees, f"{degrees}°")


class MonitorCanvas(QGraphicsView):
    selected = Signal(str)
    moved = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#090c10"))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumHeight(430)
        self.scale_factor = 0.13
        self.origin = QPointF(700, 450)
        self.items_by_device: dict[str, MonitorItem] = {}
        self.monitors: list[MonitorInfo] = []
        self.scene_obj.setSceneRect(-1200, -900, 3800, 2600)

    def load_monitors(self, monitors: list[MonitorInfo]) -> None:
        self.scene_obj.clear()
        self.items_by_device.clear()
        self.monitors = monitors

        for monitor in monitors:
            item = MonitorItem(
                monitor,
                self.scale_factor,
                self._select_from_item,
                self._moved_from_item,
            )
            item.setPos(
                self.origin.x() + monitor.left * self.scale_factor,
                self.origin.y() + monitor.top * self.scale_factor,
            )
            self.scene_obj.addItem(item)
            self.items_by_device[monitor.device] = item

        if monitors:
            self.select_device(monitors[0].device)
            bounds = self.scene_obj.itemsBoundingRect().adjusted(-80, -80, 80, 80)
            self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def _select_from_item(self, device: str) -> None:
        self.select_device(device)
        self.selected.emit(device)

    def _moved_from_item(self, device: str) -> None:
        self.moved.emit(device)

    def select_device(self, device: str) -> None:
        for dev, item in self.items_by_device.items():
            item.set_selected_visual(dev == device)

    def _primary_item(self) -> MonitorItem | None:
        return next(
            (item for item in self.items_by_device.values() if item.monitor.primary),
            None,
        )

    def pending_position(self, device: str) -> tuple[int, int]:
        item = self.items_by_device[device]
        primary = self._primary_item()
        if primary is None:
            origin = self.origin
        else:
            origin = primary.pos()
        x = round((item.pos().x() - origin.x()) / self.scale_factor)
        y = round((item.pos().y() - origin.y()) / self.scale_factor)
        return x, y

    def set_pending_position(self, device: str, x: int, y: int) -> None:
        item = self.items_by_device[device]
        primary = self._primary_item()
        anchor = primary.pos() if primary is not None else self.origin
        item.setPos(
            anchor.x() + int(x) * self.scale_factor,
            anchor.y() + int(y) * self.scale_factor,
        )

    def set_pending_orientation(self, device: str, orientation: int) -> None:
        item = self.items_by_device.get(device)
        if item is not None:
            item.update_geometry(orientation)

    def layout_payload(self) -> list[dict[str, int | str]]:
        payload: list[dict[str, int | str]] = []
        for monitor in self.monitors:
            item = self.items_by_device[monitor.device]
            x, y = self.pending_position(monitor.device)
            payload.append(
                {
                    "device": monitor.device,
                    "x": x,
                    "y": y,
                    "orientation": item.pending_orientation,
                }
            )
        return payload


class MonitorPage(QWidget):
    status = Signal(str)
    request_disable_monitor = Signal(str)
    request_enable_monitor = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.monitors: list[MonitorInfo] = []
        self.selected_device = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        left = QVBoxLayout()
        toolbar = QHBoxLayout()
        title = QLabel("Distribución de pantallas")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self.refresh_button = QPushButton("Actualizar")
        self.apply_button = QPushButton("Aplicar distribución")
        self.apply_button.setObjectName("PrimaryButton")
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.apply_button)
        left.addLayout(toolbar)

        self.canvas = MonitorCanvas()
        left.addWidget(self.canvas, 1)

        hint = QLabel(
            "Arrastrá cada pantalla hasta la posición deseada. "
            "El monitor principal permanece como referencia 0,0 de Windows."
        )
        hint.setStyleSheet("color: #8b949e;")
        hint.setWordWrap(True)
        left.addWidget(hint)

        control_card = QFrame()
        control_card.setObjectName("Card")
        control_card.setFixedWidth(330)
        controls = QVBoxLayout(control_card)
        controls.setContentsMargins(18, 18, 18, 18)

        self.monitor_name = QLabel("Sin monitor")
        self.monitor_name.setStyleSheet("font-size: 14pt; font-weight: 700;")
        self.monitor_meta = QLabel("")
        self.monitor_meta.setStyleSheet("color: #8b949e;")
        self.monitor_meta.setWordWrap(True)
        controls.addWidget(self.monitor_name)
        controls.addWidget(self.monitor_meta)

        form = QFormLayout()
        self.orientation_combo = QComboBox()
        for label, degrees in (
            ("Horizontal", 0),
            ("Vertical", 90),
            ("Horizontal invertida", 180),
            ("Vertical invertida", 270),
        ):
            self.orientation_combo.addItem(label, degrees)

        self.x_spin = QSpinBox()
        self.x_spin.setRange(-20000, 20000)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-20000, 20000)
        form.addRow("Orientación", self.orientation_combo)
        form.addRow("Posición X", self.x_spin)
        form.addRow("Posición Y", self.y_spin)
        controls.addLayout(form)

        controls.addSpacing(10)
        brightness_title = QLabel("Brillo")
        brightness_title.setStyleSheet("font-weight: 700;")
        controls.addWidget(brightness_title)

        bright_row = QHBoxLayout()
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness_value = QLabel("—")
        self.brightness_value.setFixedWidth(42)
        bright_row.addWidget(self.brightness)
        bright_row.addWidget(self.brightness_value)
        controls.addLayout(bright_row)

        self.ddc_status = QLabel("")
        self.ddc_status.setWordWrap(True)
        self.ddc_status.setStyleSheet("color: #8b949e;")
        controls.addWidget(self.ddc_status)

        self.power_off = QPushButton("Apagar este monitor")
        self.power_off.setObjectName("DangerButton")
        controls.addWidget(self.power_off)

        controls.addSpacing(12)
        disabled_title = QLabel("Monitores apagados")
        disabled_title.setStyleSheet("font-weight: 700;")
        controls.addWidget(disabled_title)
        self.disabled_combo = QComboBox()
        self.enable_disabled = QPushButton("Encender monitor seleccionado")
        controls.addWidget(self.disabled_combo)
        controls.addWidget(self.enable_disabled)
        controls.addStretch()

        root.addLayout(left, 1)
        root.addWidget(control_card)

        self.refresh_button.clicked.connect(self.refresh)
        self.apply_button.clicked.connect(self.apply_layout)
        self.canvas.selected.connect(self.select_monitor)
        self.canvas.moved.connect(self.sync_position_controls)
        self.orientation_combo.currentIndexChanged.connect(self.orientation_changed)
        self.x_spin.editingFinished.connect(self.position_changed)
        self.y_spin.editingFinished.connect(self.position_changed)
        self.brightness.sliderReleased.connect(self.brightness_changed)
        self.power_off.clicked.connect(self.request_disable_selected)
        self.enable_disabled.clicked.connect(self.request_enable_selected)

        self.refresh()

    def monitor_by_device(self, device: str) -> MonitorInfo | None:
        return next((m for m in self.monitors if m.device == device), None)

    def refresh(self) -> None:
        self.monitors = enum_monitors()
        reconcile_active_devices({monitor.device for monitor in self.monitors})
        self.refresh_disabled()
        self.canvas.load_monitors(self.monitors)
        if self.monitors:
            preferred = self.selected_device
            if not any(m.device == preferred for m in self.monitors):
                preferred = self.monitors[0].device
            self.select_monitor(preferred)
            self.status.emit(f"{len(self.monitors)} pantalla(s) activa(s)")
        else:
            self.selected_device = ""
            self.monitor_name.setText("No se detectaron pantallas")

    def select_monitor(self, device: str) -> None:
        monitor = self.monitor_by_device(device)
        if monitor is None:
            return
        self.selected_device = device
        self.canvas.select_device(device)
        self.monitor_name.setText(monitor.name)
        self.monitor_meta.setText(
            f"{monitor.device}\n"
            f"{monitor.width} × {monitor.height} · {monitor.orientation_label}"
            + (" · Principal" if monitor.primary else "")
        )

        idx = self.orientation_combo.findData(
            self.canvas.items_by_device[device].pending_orientation
        )
        self.orientation_combo.blockSignals(True)
        self.orientation_combo.setCurrentIndex(max(0, idx))
        self.orientation_combo.blockSignals(False)
        self.sync_position_controls(device)
        self.load_brightness()
        self.power_off.setEnabled(len(self.monitors) > 1)
        if len(self.monitors) <= 1:
            self.power_off.setToolTip("No se puede apagar la última pantalla activa.")
        else:
            self.power_off.setToolTip("")

    def sync_position_controls(self, _device: str = "") -> None:
        if not self.selected_device:
            return
        x, y = self.canvas.pending_position(self.selected_device)
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)

    def position_changed(self) -> None:
        if not self.selected_device:
            return
        self.canvas.set_pending_position(
            self.selected_device,
            self.x_spin.value(),
            self.y_spin.value(),
        )

    def orientation_changed(self) -> None:
        if not self.selected_device:
            return
        degrees = int(self.orientation_combo.currentData())
        self.canvas.set_pending_orientation(self.selected_device, degrees)

    def apply_layout(self) -> None:
        if not self.monitors:
            return
        ok, message = apply_monitor_layout(self.canvas.layout_payload())
        self.status.emit(message)
        if not ok:
            QMessageBox.warning(self, "No se pudo aplicar", message)
            return
        QTimer.singleShot(1200, self.refresh)

    def load_brightness(self) -> None:
        monitor = self.monitor_by_device(self.selected_device)
        if monitor is None:
            return
        value = get_monitor_brightness(monitor.handle)
        if value is None:
            self.brightness.setEnabled(False)
            self.brightness_value.setText("—")
            self.ddc_status.setText(
                "Este monitor no expone brillo por DDC/CI o el canal está deshabilitado."
            )
        else:
            self.brightness.setEnabled(True)
            self.brightness.setValue(value)
            self.brightness_value.setText(f"{value}%")
            self.ddc_status.setText("DDC/CI disponible para este monitor.")

    def brightness_changed(self) -> None:
        monitor = self.monitor_by_device(self.selected_device)
        if monitor is None:
            return
        value = self.brightness.value()
        if set_monitor_brightness(monitor.handle, value):
            self.brightness_value.setText(f"{value}%")
            self.status.emit(f"Brillo de {monitor.name}: {value}%")
        else:
            self.load_brightness()
            self.status.emit("El monitor rechazó el cambio de brillo.")

    def refresh_disabled(self) -> None:
        current = self.disabled_combo.currentData() if hasattr(self, "disabled_combo") else None
        profiles = load_disabled_monitors()
        if hasattr(self, "disabled_combo"):
            self.disabled_combo.clear()
            for device, profile in profiles.items():
                self.disabled_combo.addItem(
                    str(profile.get("name") or device),
                    device,
                )
            if current:
                idx = self.disabled_combo.findData(current)
                if idx >= 0:
                    self.disabled_combo.setCurrentIndex(idx)
            self.disabled_combo.setEnabled(bool(profiles))
            self.enable_disabled.setEnabled(bool(profiles))

    def request_disable_selected(self) -> None:
        if not self.selected_device:
            return
        if len(self.monitors) <= 1:
            QMessageBox.information(
                self,
                "Última pantalla activa",
                "Pantallas no permite apagar la última pantalla activa.",
            )
            return
        self.request_disable_monitor.emit(self.selected_device)

    def request_enable_selected(self) -> None:
        device = self.disabled_combo.currentData()
        if device:
            self.request_enable_monitor.emit(str(device))


class WindowRulesPage(QWidget):
    status = Signal(str)

    def __init__(self, store: RuleStore, enforcer: RuleEnforcer) -> None:
        super().__init__()
        self.store = store
        self.enforcer = enforcer
        self.windows: list[WindowInfo] = []
        self.monitors: list[MonitorInfo] = []
        self.current_window: WindowInfo | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Ventanas y reglas")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.auto_check = QCheckBox("Bloqueo automático")
        self.auto_check.setChecked(True)
        self.enforcer_status = QLabel("")
        self.enforcer_status.setStyleSheet("color: #8b949e;")
        self.refresh_windows_button = QPushButton("Actualizar ventanas")
        header.addWidget(self.enforcer_status)
        header.addWidget(self.auto_check)
        header.addWidget(self.refresh_windows_button)
        root.addLayout(header)

        self.windows_table = QTableWidget(0, 4)
        self.windows_table.setHorizontalHeaderLabels(
            ["Aplicación", "Título", "Pantalla", "Tamaño"]
        )
        self.windows_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.windows_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.windows_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.windows_table.setAlternatingRowColors(True)
        self.windows_table.verticalHeader().setVisible(False)
        wh = self.windows_table.horizontalHeader()
        wh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        wh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        wh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.windows_table, 1)

        editor = QFrame()
        editor.setObjectName("Card")
        editor_layout = QGridLayout(editor)
        editor_layout.setContentsMargins(14, 14, 14, 14)

        self.selected_label = QLabel("Seleccioná una ventana de la lista.")
        self.selected_label.setStyleSheet("font-weight: 700;")
        editor_layout.addWidget(self.selected_label, 0, 0, 1, 6)

        self.monitor_combo = QComboBox()
        self.title_filter = QLineEdit()
        self.title_filter.setPlaceholderText("Opcional, por ejemplo: Discord")

        self.x_pct = self._pct_spin(-100, 100, 0)
        self.y_pct = self._pct_spin(-100, 100, 0)
        self.w_pct = self._pct_spin(5, 200, 50)
        self.h_pct = self._pct_spin(5, 200, 100)

        editor_layout.addWidget(QLabel("Monitor"), 1, 0)
        editor_layout.addWidget(self.monitor_combo, 1, 1)
        editor_layout.addWidget(QLabel("Filtro de título"), 1, 2)
        editor_layout.addWidget(self.title_filter, 1, 3, 1, 3)

        editor_layout.addWidget(QLabel("X %"), 2, 0)
        editor_layout.addWidget(self.x_pct, 2, 1)
        editor_layout.addWidget(QLabel("Y %"), 2, 2)
        editor_layout.addWidget(self.y_pct, 2, 3)
        editor_layout.addWidget(QLabel("Ancho %"), 2, 4)
        editor_layout.addWidget(self.w_pct, 2, 5)

        editor_layout.addWidget(QLabel("Alto %"), 3, 0)
        editor_layout.addWidget(self.h_pct, 3, 1)

        self.capture_button = QPushButton("Capturar posición actual")
        self.save_rule_button = QPushButton("Guardar regla")
        self.save_rule_button.setObjectName("PrimaryButton")
        editor_layout.addWidget(self.capture_button, 3, 4)
        editor_layout.addWidget(self.save_rule_button, 3, 5)
        root.addWidget(editor)

        rules_title = QLabel("Reglas guardadas")
        rules_title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        root.addWidget(rules_title)

        self.rules_table = QTableWidget(0, 6)
        self.rules_table.setHorizontalHeaderLabels(
            ["Activa", "Aplicación", "Filtro", "Pantalla", "Zona", ""]
        )
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.verticalHeader().setVisible(False)
        rh = self.rules_table.horizontalHeader()
        rh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        rh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        rh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        rh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.rules_table)

        self.refresh_windows_button.clicked.connect(self.refresh_windows)
        self.windows_table.itemSelectionChanged.connect(self.window_selected)
        self.capture_button.clicked.connect(self.capture_current_position)
        self.save_rule_button.clicked.connect(self.save_rule)
        self.auto_check.toggled.connect(self.enforcer.set_active)
        self.enforcer.status_changed.connect(self.enforcer_status.setText)
        self.store.changed.connect(self.refresh_rules)

        self.refresh_windows()
        self.refresh_rules()
        QTimer.singleShot(0, lambda: self.enforcer.set_active(True))

    @staticmethod
    def _pct_spin(low: float, high: float, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" %")
        spin.setValue(value)
        return spin

    def refresh_monitors(self) -> None:
        current = self.monitor_combo.currentData()
        self.monitors = enum_monitors()
        self.monitor_combo.clear()
        for monitor in self.monitors:
            self.monitor_combo.addItem(
                f"{monitor.name} · {monitor.width}×{monitor.height}",
                monitor.device,
            )
        if current:
            idx = self.monitor_combo.findData(current)
            if idx >= 0:
                self.monitor_combo.setCurrentIndex(idx)

    def refresh_windows(self) -> None:
        self.refresh_monitors()
        self.windows = enum_windows()
        self.windows_table.setRowCount(len(self.windows))
        monitor_names = {m.device: m.name for m in self.monitors}

        for row, window in enumerate(self.windows):
            app_item = QTableWidgetItem(window.process_name)
            app_item.setData(Qt.ItemDataRole.UserRole, row)
            self.windows_table.setItem(row, 0, app_item)
            self.windows_table.setItem(row, 1, QTableWidgetItem(window.title))
            self.windows_table.setItem(
                row,
                2,
                QTableWidgetItem(monitor_names.get(window.monitor_device, window.monitor_device)),
            )
            self.windows_table.setItem(
                row,
                3,
                QTableWidgetItem(f"{window.width}×{window.height}"),
            )

        self.status.emit(f"{len(self.windows)} ventana(s) visible(s) detectada(s)")

    def window_selected(self) -> None:
        rows = self.windows_table.selectionModel().selectedRows()
        if not rows:
            self.current_window = None
            return
        row = rows[0].row()
        if not (0 <= row < len(self.windows)):
            return
        self.current_window = self.windows[row]
        self.selected_label.setText(
            f"{self.current_window.process_name} — {self.current_window.title}"
        )
        idx = self.monitor_combo.findData(self.current_window.monitor_device)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)
        self.capture_current_position()

    def selected_monitor(self) -> MonitorInfo | None:
        device = self.monitor_combo.currentData()
        return next((m for m in self.monitors if m.device == device), None)

    def capture_current_position(self) -> None:
        window = self.current_window
        if window is None:
            return
        monitor = next(
            (m for m in self.monitors if m.device == window.monitor_device),
            self.selected_monitor(),
        )
        if monitor is None or monitor.work_width <= 0 or monitor.work_height <= 0:
            return

        idx = self.monitor_combo.findData(monitor.device)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)

        self.x_pct.setValue((window.left - monitor.work_left) * 100 / monitor.work_width)
        self.y_pct.setValue((window.top - monitor.work_top) * 100 / monitor.work_height)
        self.w_pct.setValue(window.width * 100 / monitor.work_width)
        self.h_pct.setValue(window.height * 100 / monitor.work_height)

    def save_rule(self) -> None:
        if self.current_window is None:
            QMessageBox.information(
                self,
                "Elegí una ventana",
                "Primero seleccioná la aplicación o ventana que querés fijar.",
            )
            return
        monitor = self.selected_monitor()
        if monitor is None:
            return

        self.store.add_from_window(
            self.current_window,
            monitor,
            title_contains=self.title_filter.text(),
            x_pct=self.x_pct.value(),
            y_pct=self.y_pct.value(),
            width_pct=self.w_pct.value(),
            height_pct=self.h_pct.value(),
        )
        self.enforcer.enforce_once()
        self.status.emit(
            f"Regla creada para {self.current_window.process_name} en {monitor.name}."
        )

    def refresh_rules(self) -> None:
        rules = self.store.rules
        self.rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            enabled = QCheckBox()
            enabled.setChecked(rule.enabled)
            enabled.toggled.connect(partial(self.store.set_enabled, rule.id))
            self.rules_table.setCellWidget(row, 0, enabled)
            self.rules_table.setItem(row, 1, QTableWidgetItem(rule.process_name))
            self.rules_table.setItem(
                row, 2, QTableWidgetItem(rule.title_contains or "Cualquier título")
            )
            self.rules_table.setItem(row, 3, QTableWidgetItem(rule.monitor_name))
            self.rules_table.setItem(
                row,
                4,
                QTableWidgetItem(
                    f"{rule.x_pct:.0f},{rule.y_pct:.0f} · "
                    f"{rule.width_pct:.0f}×{rule.height_pct:.0f}%"
                ),
            )
            delete = QPushButton("Eliminar")
            delete.setObjectName("DangerButton")
            delete.clicked.connect(partial(self.store.remove, rule.id))
            self.rules_table.setCellWidget(row, 5, delete)


class SettingsPage(QWidget):
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        prefs = load_preferences()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        title = QLabel("Configuración")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)

        self.start_with_windows = QCheckBox("Iniciar Pantallas con Windows")
        self.start_minimized = QCheckBox("Iniciar minimizada en la bandeja")
        self.start_with_windows.setChecked(startup_is_registered())
        self.start_minimized.setChecked(bool(prefs.get("start_minimized", True)))

        note = QLabel(
            "Cuando el inicio minimizado está activo, Pantallas arranca en la bandeja "
            "y las reglas de ventanas siguen funcionando sin abrir la ventana principal."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")

        layout.addWidget(self.start_with_windows)
        layout.addWidget(self.start_minimized)
        layout.addWidget(note)
        root.addWidget(card)
        root.addStretch()

        self.start_with_windows.toggled.connect(self._startup_changed)
        self.start_minimized.toggled.connect(self._minimized_changed)

    def _startup_changed(self, enabled: bool) -> None:
        ok, message = set_windows_startup(
            enabled,
            start_minimized=self.start_minimized.isChecked(),
        )
        if not ok:
            self.start_with_windows.blockSignals(True)
            self.start_with_windows.setChecked(not enabled)
            self.start_with_windows.blockSignals(False)
        self.status.emit(message)

    def _minimized_changed(self, enabled: bool) -> None:
        if self.start_with_windows.isChecked():
            ok, message = set_windows_startup(
                True,
                start_minimized=enabled,
            )
            if not ok:
                self.start_minimized.blockSignals(True)
                self.start_minimized.setChecked(not enabled)
                self.start_minimized.blockSignals(False)
                self.status.emit(message)
                return
        else:
            save_preferences(
                start_with_windows=False,
                start_minimized=enabled,
            )
        self.status.emit(
            "Inicio minimizado activado."
            if enabled
            else "Pantallas se abrirá visible al iniciar con Windows."
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pantallas")
        self.resize(1240, 800)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(APP_STYLE)

        self.store = RuleStore()
        self.enforcer = RuleEnforcer(self.store)

        self.tabs = QTabWidget()
        self.monitor_page = MonitorPage()
        self.rules_page = WindowRulesPage(self.store, self.enforcer)
        self.settings_page = SettingsPage()
        self.tabs.addTab(self.monitor_page, "Pantallas")
        self.tabs.addTab(self.rules_page, "Ventanas y reglas")
        self.tabs.addTab(self.settings_page, "Configuración")
        self.setCentralWidget(self.tabs)

        self.monitor_page.status.connect(self.statusBar().showMessage)
        self.monitor_page.request_disable_monitor.connect(self.disable_monitor_from_ui)
        self.monitor_page.request_enable_monitor.connect(self.enable_monitor_from_ui)
        self.rules_page.status.connect(self.statusBar().showMessage)
        self.settings_page.status.connect(self.statusBar().showMessage)
        self.statusBar().showMessage("Listo")

        self.version_label = QLabel(
            f"v{__version__} · build {BUILD_ID}" if BUILD_ID else f"v{__version__} · desarrollo"
        )
        self.version_label.setStyleSheet("color: #8b949e; padding: 0 8px;")
        self.update_button = QPushButton("Buscar actualizaciones")
        self.update_button.setToolTip(
            "Descarga la última versión, cierra Pantallas, la instala y vuelve a abrirla."
        )
        self.statusBar().addPermanentWidget(self.version_label)
        self.statusBar().addPermanentWidget(self.update_button)

        self._update_worker: UpdateWorker | None = None
        self._update_manual = False
        self.update_button.clicked.connect(lambda: self.check_for_updates(manual=True))

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(30 * 60 * 1000)
        self.update_timer.timeout.connect(lambda: self.check_for_updates(manual=False))
        self.update_timer.start()
        QTimer.singleShot(5000, lambda: self.check_for_updates(manual=False))

        self._really_quit = False
        self.tray = QSystemTrayIcon(self)
        tray_icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(tray_icon)
        self.tray.setIcon(tray_icon)
        self.tray.setToolTip("Pantallas")

        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.rebuild_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def check_for_updates(self, manual: bool = False) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            if manual:
                self.statusBar().showMessage("Ya hay una comprobación de actualización en curso.")
            return

        self._update_manual = manual
        self.update_button.setEnabled(False)
        self.update_button.setText("Buscando…")

        worker = UpdateWorker(self)
        self._update_worker = worker
        worker.status.connect(self._update_status)
        worker.progress.connect(self._update_progress)
        worker.no_update.connect(self._no_update_available)
        worker.installer_ready.connect(self._installer_ready)
        worker.failed.connect(self._update_failed)
        worker.finished.connect(self._update_finished)
        worker.start()

    def _update_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _update_progress(self, percent: int) -> None:
        self.update_button.setText(f"Descargando {percent}%")

    def _no_update_available(self, latest_build: int) -> None:
        message = "Pantallas ya está actualizado."
        if BUILD_ID:
            message += f" Build actual: {BUILD_ID}."
        self.statusBar().showMessage(message, 5000)
        if self._update_manual:
            QMessageBox.information(self, "Sin actualizaciones", message)

    def _update_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Actualización: {message}", 7000)
        if self._update_manual:
            QMessageBox.warning(self, "No se pudo actualizar", message)

    def _installer_ready(self, installer_path: str, latest_build: int) -> None:
        self.statusBar().showMessage(
            f"Instalando build {latest_build}. Pantallas se reiniciará…"
        )
        if not launch_installer_after_exit(installer_path):
            self._update_failed("No se pudo iniciar el instalador descargado.")
            return

        self._really_quit = True
        self.enforcer.set_active(False)
        self.update_timer.stop()
        self.tray.hide()
        QApplication.instance().quit()

    def _update_finished(self) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("Buscar actualizaciones")
        worker = self._update_worker
        self._update_worker = None
        if worker is not None:
            worker.deleteLater()

    def _move_window_to_monitor(self, device: str) -> None:
        monitor = next((m for m in enum_monitors() if m.device == device), None)
        if monitor is None:
            return
        width = min(max(self.width(), self.minimumWidth()), max(700, monitor.work_width - 80))
        height = min(max(self.height(), self.minimumHeight()), max(520, monitor.work_height - 80))
        self.showNormal()
        self.resize(width, height)
        self.move(monitor.work_left + 40, monitor.work_top + 40)
        QApplication.processEvents()

    def open_monitor_from_tray(self, device: str) -> None:
        self.show_from_tray()
        self.tabs.setCurrentWidget(self.monitor_page)
        self.monitor_page.select_monitor(device)
        self._move_window_to_monitor(device)

    def disable_monitor_from_ui(self, device: str) -> None:
        active = enum_monitors()
        target = next((m for m in active if m.device == device), None)
        if target is None:
            self.statusBar().showMessage("La pantalla ya no está activa.", 5000)
            self.monitor_page.refresh()
            return
        alternatives = [m for m in active if m.device != device]
        if not alternatives:
            QMessageBox.information(
                self,
                "Última pantalla activa",
                "No se puede apagar la última pantalla activa.",
            )
            return

        fallback = alternatives[0]
        if self.isVisible():
            self._move_window_to_monitor(fallback.device)

        ok, message, profile = disable_monitor(device)
        if ok and profile is not None:
            save_disabled_monitor(profile)
            self.statusBar().showMessage(message, 5000)
            self.tray.showMessage(
                "Monitor apagado",
                f"{target.name} fue desactivado. Podés volver a encenderlo desde el menú de Pantallas.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            QTimer.singleShot(900, self.refresh_monitor_views)
        else:
            QMessageBox.warning(self, "No se pudo apagar", message)

    def enable_monitor_from_ui(self, device: str) -> None:
        profile = load_disabled_monitors().get(device)
        if profile is None:
            self.statusBar().showMessage("No se encontró la configuración guardada de esa pantalla.", 5000)
            return

        ok, message = enable_monitor(profile)
        if ok:
            remove_disabled_monitor(device)
            self.statusBar().showMessage(message, 5000)
            QTimer.singleShot(1200, self.refresh_monitor_views)
        else:
            QMessageBox.warning(self, "No se pudo encender", message)

    def refresh_monitor_views(self) -> None:
        self.monitor_page.refresh()
        self.rules_page.refresh_monitors()

    def set_tray_brightness(self, device: str, percent: int) -> None:
        monitor = next((m for m in enum_monitors() if m.device == device), None)
        if monitor is None:
            self.tray.showMessage("Pantallas", "Ese monitor ya no está activo.")
            return
        if set_monitor_brightness(monitor.handle, percent):
            self.statusBar().showMessage(f"Brillo de {monitor.name}: {percent}%", 4000)
            if self.monitor_page.selected_device == device:
                self.monitor_page.load_brightness()
        else:
            self.tray.showMessage(
                "Brillo no disponible",
                f"{monitor.name} no aceptó el cambio de brillo por DDC/CI.",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )

    def rebuild_tray_menu(self) -> None:
        self.tray_menu.clear()

        open_action = self.tray_menu.addAction("Abrir Pantallas")
        open_action.triggered.connect(self.show_from_tray)
        self.tray_menu.addSeparator()

        active = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in active})

        for monitor in active:
            suffix = " · principal" if monitor.primary else ""
            submenu = self.tray_menu.addMenu(f"{monitor.name}{suffix}")

            configure = submenu.addAction("Abrir y configurar aquí")
            configure.triggered.connect(
                lambda _checked=False, device=monitor.device: self.open_monitor_from_tray(device)
            )

            brightness_menu = submenu.addMenu("Brillo")
            for value in (25, 50, 75, 100):
                action = brightness_menu.addAction(f"{value}%")
                action.triggered.connect(
                    lambda _checked=False, device=monitor.device, pct=value:
                        self.set_tray_brightness(device, pct)
                )

            submenu.addSeparator()
            off_action = submenu.addAction("Apagar monitor")
            off_action.setEnabled(len(active) > 1)
            if len(active) <= 1:
                off_action.setToolTip("No se puede apagar la última pantalla activa.")
            off_action.triggered.connect(
                lambda _checked=False, device=monitor.device: self.disable_monitor_from_ui(device)
            )

        if disabled:
            self.tray_menu.addSeparator()
            for device, profile in disabled.items():
                submenu = self.tray_menu.addMenu(
                    f"{profile.get('name', device)} · apagado"
                )
                on_action = submenu.addAction("Encender monitor")
                on_action.triggered.connect(
                    lambda _checked=False, dev=device: self.enable_monitor_from_ui(dev)
                )

        self.tray_menu.addSeparator()
        prefs = load_preferences()

        startup_action = self.tray_menu.addAction("Iniciar con Windows")
        startup_action.setCheckable(True)
        startup_action.setChecked(startup_is_registered())
        startup_action.toggled.connect(
            lambda enabled: self.settings_page.start_with_windows.setChecked(enabled)
        )

        minimized_action = self.tray_menu.addAction("Iniciar minimizada")
        minimized_action.setCheckable(True)
        minimized_action.setChecked(bool(prefs.get("start_minimized", True)))
        minimized_action.toggled.connect(
            lambda enabled: self.settings_page.start_minimized.setChecked(enabled)
        )

        self.tray_menu.addSeparator()
        update_action = self.tray_menu.addAction("Buscar actualizaciones")
        update_action.triggered.connect(lambda: self.check_for_updates(manual=True))

        quit_action = self.tray_menu.addAction("Salir")
        quit_action.triggered.connect(self.quit_app)

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def quit_app(self) -> None:
        self._really_quit = True
        self.enforcer.set_active(False)
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._really_quit or not QSystemTrayIcon.isSystemTrayAvailable():
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Pantallas sigue activo",
            "Las reglas de posición continúan funcionando desde la bandeja.",
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )
