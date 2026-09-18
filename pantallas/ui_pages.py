from __future__ import annotations

from functools import partial

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .build_info import BUILD_ID
from .models import MonitorInfo, WindowInfo
from .monitor_aliases import (
    display_name_for_device,
    monitor_display_name,
    set_monitor_alias,
)
from .monitor_state import load_disabled_monitors, reconcile_active_devices
from .preferences import (
    load_preferences,
    save_preferences,
    set_windows_startup,
    startup_is_registered,
)
from .rules import RuleEnforcer, RuleStore
from .ui_theme import Card, StatCard, danger_button, primary_button
from .windows_api import (
    apply_monitor_layout,
    enum_monitors,
    enum_windows,
    get_monitor_brightness,
    set_monitor_brightness,
)


def _page_header(title: str, subtitle: str) -> tuple[QWidget, QHBoxLayout]:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    texts = QVBoxLayout()
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)
    texts.addWidget(title_label)
    texts.addWidget(subtitle_label)
    layout.addLayout(texts, 1)
    return box, layout


def _content_scroll(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


class DashboardPage(QWidget):
    navigate = Signal(str)
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(18)

        header, h = _page_header(
            "Inicio",
            "Tu centro de control para pantallas, ventanas y automatizaciones.",
        )
        refresh = QPushButton("Actualizar estado")
        refresh.clicked.connect(self.refresh_requested)
        h.addWidget(refresh)
        root.addWidget(header)

        stats = QHBoxLayout()
        self.active_stat = StatCard("Monitores activos", "—")
        self.off_stat = StatCard("Monitores apagados", "—")
        self.rules_stat = StatCard("Reglas activas", "—")
        self.startup_stat = StatCard("Inicio con Windows", "—")
        for card in (
            self.active_stat,
            self.off_stat,
            self.rules_stat,
            self.startup_stat,
        ):
            stats.addWidget(card)
        root.addLayout(stats)

        quick = Card("Acciones rápidas", "Las tareas más usadas, sin navegar por menús.")
        quick_row = QHBoxLayout()
        for text, page in (
            ("Administrar monitores", "monitors"),
            ("Acomodar distribución", "monitor-layout"),
            ("Fijar una aplicación", "windows"),
            ("Buscar actualizaciones", "updates"),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, p=page: self.navigate.emit(p))
            quick_row.addWidget(button)
        quick.body.addLayout(quick_row)
        root.addWidget(quick)

        info = Card("Estado del sistema")
        self.summary = QLabel("Cargando información…")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("Muted")
        info.body.addWidget(self.summary)
        root.addWidget(info)
        root.addStretch()

    def refresh_view(self, store: RuleStore) -> None:
        monitors = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in monitors})
        active_rules = sum(1 for rule in store.rules if rule.enabled)
        startup = startup_is_registered()

        self.active_stat.value_label.setText(str(len(monitors)))
        self.off_stat.value_label.setText(str(len(disabled)))
        self.rules_stat.value_label.setText(str(active_rules))
        self.startup_stat.value_label.setText("Sí" if startup else "No")

        primary = next((m for m in monitors if m.primary), None)
        primary_text = monitor_display_name(primary) if primary else "sin identificar"
        self.summary.setText(
            f"Monitor principal: {primary_text}. "
            f"Hay {len(monitors)} pantalla(s) activa(s), {len(disabled)} apagada(s) "
            f"y {active_rules} regla(s) de ventana activa(s)."
        )


class MonitorControlCard(Card):
    disable_requested = Signal(str)
    configure_requested = Signal(str)
    brightness_changed = Signal(str, int)
    renamed = Signal()

    def __init__(self, monitor: MonitorInfo, active_count: int) -> None:
        title = monitor_display_name(monitor) + ("  ·  Principal" if monitor.primary else "")
        super().__init__(title)
        self.monitor = monitor

        meta = QLabel(
            f"{monitor.width} × {monitor.height}  ·  {monitor.orientation_label}  ·  "
            f"Posición {monitor.left}, {monitor.top}"
        )
        meta.setObjectName("Muted")
        self.body.addWidget(meta)

        row = QHBoxLayout()
        bright_label = QLabel("Brillo")
        bright_label.setFixedWidth(45)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.value = QLabel("—")
        self.value.setFixedWidth(44)
        row.addWidget(bright_label)
        row.addWidget(self.slider, 1)
        row.addWidget(self.value)
        self.body.addLayout(row)

        brightness = get_monitor_brightness(monitor.handle)
        if brightness is None:
            self.slider.setEnabled(False)
            self.value.setText("N/D")
            self.slider.setToolTip("Este monitor no expone brillo por DDC/CI.")
        else:
            self.slider.setValue(brightness)
            self.value.setText(f"{brightness}%")
            self.slider.sliderReleased.connect(self._brightness_released)

        actions = QHBoxLayout()
        rename = QPushButton("Cambiar nombre")
        rename.clicked.connect(self._rename)
        configure = QPushButton("Configurar")
        configure.clicked.connect(
            lambda: self.configure_requested.emit(self.monitor.device)
        )
        disable = danger_button("Apagar")
        disable.setEnabled(active_count > 1)
        disable.setToolTip(
            "" if active_count > 1 else "No se puede apagar la última pantalla activa."
        )
        disable.clicked.connect(lambda: self.disable_requested.emit(self.monitor.device))
        actions.addWidget(rename)
        actions.addWidget(configure)
        actions.addWidget(disable)
        actions.addStretch()
        self.body.addLayout(actions)

    def _brightness_released(self) -> None:
        value = self.slider.value()
        self.value.setText(f"{value}%")
        self.brightness_changed.emit(self.monitor.device, value)

    def _rename(self) -> None:
        current = monitor_display_name(self.monitor)
        alias, accepted = QInputDialog.getText(
            self,
            "Nombre del monitor",
            "Nombre personalizado:",
            text=current,
        )
        if not accepted:
            return
        set_monitor_alias(self.monitor.device, alias)
        self.renamed.emit()


class MonitorsPage(QWidget):
    disable_requested = Signal(str)
    enable_requested = Signal(str)
    configure_requested = Signal(str)
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 24, 26, 24)
        outer.setSpacing(16)

        header, h = _page_header(
            "Monitores",
            "Controlá cada pantalla de forma independiente y segura.",
        )
        refresh = QPushButton("Detectar nuevamente")
        refresh.clicked.connect(self.refresh)
        h.addWidget(refresh)
        outer.addWidget(header)

        container = QWidget()
        self.body = QVBoxLayout(container)
        self.body.setContentsMargins(0, 0, 8, 0)
        self.body.setSpacing(12)
        outer.addWidget(_content_scroll(container), 1)
        self.refresh()

    def _clear(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self) -> None:
        self._clear()
        all_monitors = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in all_monitors})
        monitors = [m for m in all_monitors if m.device not in disabled]

        if not monitors:
            empty = Card("No se detectaron monitores activos")
            self.body.addWidget(empty)
        else:
            active_title = QLabel(f"Activos · {len(monitors)}")
            active_title.setStyleSheet("font-size: 12pt; font-weight: 750;")
            self.body.addWidget(active_title)
            for monitor in monitors:
                card = MonitorControlCard(monitor, len(monitors))
                card.disable_requested.connect(self.disable_requested)
                card.configure_requested.connect(self.configure_requested)
                card.brightness_changed.connect(self._set_brightness)
                card.renamed.connect(self._renamed)
                self.body.addWidget(card)

        if disabled:
            off_title = QLabel(f"Apagados · {len(disabled)}")
            off_title.setStyleSheet("font-size: 12pt; font-weight: 750; margin-top: 8px;")
            self.body.addWidget(off_title)
            for device, profile in disabled.items():
                card = Card(
                    display_name_for_device(device, str(profile.get("name") or device)),
                    f"{profile.get('width', '—')} × {profile.get('height', '—')} · "
                    f"guardado para restauración",
                )
                row = QHBoxLayout()
                turn_on = primary_button("Encender")
                turn_on.clicked.connect(
                    lambda _=False, dev=device: self.enable_requested.emit(dev)
                )
                row.addWidget(turn_on)
                row.addStretch()
                card.body.addLayout(row)
                self.body.addWidget(card)

        self.body.addStretch()
        self.status.emit(
            f"{len(monitors)} monitor(es) activo(s), {len(disabled)} apagado(s)."
        )

    def _renamed(self) -> None:
        self.status.emit("Nombre del monitor actualizado.")
        self.refresh()

    def _set_brightness(self, device: str, value: int) -> None:
        monitor = next((m for m in enum_monitors() if m.device == device), None)
        if monitor is None:
            self.status.emit("El monitor ya no está activo.")
            self.refresh()
            return
        if set_monitor_brightness(monitor.handle, value):
            self.status.emit(f"Brillo de {monitor.name}: {value}%")
        else:
            self.status.emit(f"{monitor.name} rechazó el cambio de brillo.")
            self.refresh()


class MonitorItem(QGraphicsRectItem):
    def __init__(self, monitor: MonitorInfo, scale: float, select_cb, moved_cb) -> None:
        super().__init__()
        self.monitor = monitor
        self.scale_factor = scale
        self.select_cb = select_cb
        self.moved_cb = moved_cb
        self.pending_orientation = monitor.orientation

        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self.label = QGraphicsSimpleTextItem(self)
        self.label.setBrush(QColor("#f4f7fb"))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        self.label.setFont(font)
        self.update_geometry(monitor.orientation)
        self.set_selected_visual(False)

    def update_geometry(self, orientation: int) -> None:
        self.pending_orientation = orientation
        width, height = self.monitor.width, self.monitor.height
        if (self.monitor.orientation // 90) % 2 != (orientation // 90) % 2:
            width, height = height, width
        sw = max(125.0, width * self.scale_factor)
        sh = max(82.0, height * self.scale_factor)
        self.setRect(0, 0, sw, sh)
        main = " · PRINCIPAL" if self.monitor.primary else ""
        self.label.setText(
            f"{monitor_display_name(self.monitor)}{main}\n{width} × {height}\n"
            f"{orientation_label(orientation)}"
        )
        self.label.setPos(12, 10)

    def set_selected_visual(self, selected: bool) -> None:
        self.setPen(QPen(QColor("#6f96ff" if selected else "#343c4a"), 3 if selected else 2))
        self.setBrush(QColor("#1d315d" if selected else "#171d27"))

    def mousePressEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.select_cb(self.monitor.device)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
        self.moved_cb(self.monitor.device)


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
        self.setBackgroundBrush(QColor("#0a0c11"))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumHeight(500)
        self.scale_factor = 0.13
        self.origin = QPointF(700, 460)
        self.items_by_device: dict[str, MonitorItem] = {}
        self.monitors: list[MonitorInfo] = []
        self.scene_obj.setSceneRect(-1300, -900, 4000, 2700)

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
            bounds = self.scene_obj.itemsBoundingRect().adjusted(-90, -90, 90, 90)
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
        anchor = primary.pos() if primary is not None else self.origin
        return (
            round((item.pos().x() - anchor.x()) / self.scale_factor),
            round((item.pos().y() - anchor.y()) / self.scale_factor),
        )

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
        if item:
            item.update_geometry(orientation)

    def layout_payload(self) -> list[dict[str, int | str]]:
        result = []
        for monitor in self.monitors:
            item = self.items_by_device[monitor.device]
            x, y = self.pending_position(monitor.device)
            result.append(
                {
                    "device": monitor.device,
                    "x": x,
                    "y": y,
                    "orientation": item.pending_orientation,
                }
            )
        return result


class LayoutPage(QWidget):
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.monitors: list[MonitorInfo] = []
        self.selected_device = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(14)
        header, h = _page_header(
            "Distribución",
            "Arrastrá las pantallas como están físicamente en tu escritorio.",
        )
        refresh = QPushButton("Restablecer vista")
        refresh.clicked.connect(self.refresh)
        self.apply_button = primary_button("Aplicar en Windows")
        self.apply_button.clicked.connect(self.apply_layout)
        h.addWidget(refresh)
        h.addWidget(self.apply_button)
        root.addWidget(header)

        row = QHBoxLayout()
        self.canvas = MonitorCanvas()
        row.addWidget(self.canvas, 1)

        inspector = Card("Pantalla seleccionada")
        inspector.setFixedWidth(315)
        self.name = QLabel("—")
        self.name.setStyleSheet("font-size: 13pt; font-weight: 750;")
        self.meta = QLabel("—")
        self.meta.setObjectName("Muted")
        self.meta.setWordWrap(True)
        inspector.body.addWidget(self.name)
        inspector.body.addWidget(self.meta)

        form = QFormLayout()
        self.orientation = QComboBox()
        for label, degrees in (
            ("Horizontal", 0),
            ("Vertical", 90),
            ("Horizontal invertida", 180),
            ("Vertical invertida", 270),
        ):
            self.orientation.addItem(label, degrees)
        self.x = QSpinBox()
        self.x.setRange(-20000, 20000)
        self.y = QSpinBox()
        self.y.setRange(-20000, 20000)
        form.addRow("Orientación", self.orientation)
        form.addRow("X", self.x)
        form.addRow("Y", self.y)
        inspector.body.addLayout(form)

        hint = QLabel(
            "Consejo: alineá visualmente los bordes para que el mouse pase entre "
            "monitores exactamente donde esperás."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        inspector.body.addWidget(hint)
        inspector.body.addStretch()
        row.addWidget(inspector)
        root.addLayout(row, 1)

        self.canvas.selected.connect(self.select_monitor)
        self.canvas.moved.connect(self.sync_controls)
        self.orientation.currentIndexChanged.connect(self.orientation_changed)
        self.x.editingFinished.connect(self.position_changed)
        self.y.editingFinished.connect(self.position_changed)
        self.refresh()

    def refresh(self) -> None:
        self.monitors = enum_monitors()
        self.canvas.load_monitors(self.monitors)
        self.apply_button.setEnabled(bool(self.monitors))
        if self.monitors:
            target = self.selected_device
            if not any(m.device == target for m in self.monitors):
                target = self.monitors[0].device
            self.select_monitor(target)

    def select_monitor(self, device: str) -> None:
        monitor = next((m for m in self.monitors if m.device == device), None)
        if monitor is None:
            return
        self.selected_device = device
        self.canvas.select_device(device)
        self.name.setText(monitor_display_name(monitor))
        self.meta.setText(
            f"{monitor.width} × {monitor.height} · {monitor.device}"
            + (" · Principal" if monitor.primary else "")
        )
        idx = self.orientation.findData(
            self.canvas.items_by_device[device].pending_orientation
        )
        self.orientation.blockSignals(True)
        self.orientation.setCurrentIndex(max(0, idx))
        self.orientation.blockSignals(False)
        self.sync_controls(device)

    def sync_controls(self, _device: str = "") -> None:
        if not self.selected_device:
            return
        x, y = self.canvas.pending_position(self.selected_device)
        self.x.setValue(x)
        self.y.setValue(y)

    def orientation_changed(self) -> None:
        if self.selected_device:
            self.canvas.set_pending_orientation(
                self.selected_device,
                int(self.orientation.currentData()),
            )

    def position_changed(self) -> None:
        if self.selected_device:
            self.canvas.set_pending_position(
                self.selected_device,
                self.x.value(),
                self.y.value(),
            )

    def apply_layout(self) -> None:
        ok, message = apply_monitor_layout(self.canvas.layout_payload())
        self.status.emit(message)
        if not ok:
            QMessageBox.warning(self, "No se pudo aplicar", message)
        else:
            QTimer.singleShot(1000, self.refresh)


class MonitorsWorkspacePage(QWidget):
    disable_requested = Signal(str)
    enable_requested = Signal(str)
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.controls = MonitorsPage()
        self.layout = LayoutPage()
        self.tabs.addTab(self.controls, "Control")
        self.tabs.addTab(self.layout, "Distribución")
        root.addWidget(self.tabs)

        self.controls.disable_requested.connect(self.disable_requested)
        self.controls.enable_requested.connect(self.enable_requested)
        self.controls.configure_requested.connect(self.show_layout_for)
        self.controls.status.connect(self.status)
        self.layout.status.connect(self.status)

    def refresh(self) -> None:
        self.controls.refresh()
        self.layout.refresh()

    def show_controls(self) -> None:
        self.tabs.setCurrentWidget(self.controls)
        self.controls.refresh()

    def show_layout(self) -> None:
        self.tabs.setCurrentWidget(self.layout)
        self.layout.refresh()

    def show_layout_for(self, device: str) -> None:
        self.show_layout()
        self.layout.select_monitor(device)


class RulesPage(QWidget):
    status = Signal(str)

    PRESETS = {
        "Personalizado": None,
        "Pantalla completa": (0, 0, 100, 100),
        "Mitad izquierda": (0, 0, 50, 100),
        "Mitad derecha": (50, 0, 50, 100),
        "Mitad superior": (0, 0, 100, 50),
        "Mitad inferior": (0, 50, 100, 50),
        "Centro 70%": (15, 15, 70, 70),
    }

    def __init__(self, store: RuleStore, enforcer: RuleEnforcer) -> None:
        super().__init__()
        self.store = store
        self.enforcer = enforcer
        self.windows: list[WindowInfo] = []
        self.monitors: list[MonitorInfo] = []
        self.current_window: WindowInfo | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(14)

        header, h = _page_header(
            "Ventanas y reglas",
            "Elegí dónde debe vivir cada aplicación y Pantallas la mantendrá ahí.",
        )
        self.auto = QCheckBox("Bloqueo automático")
        self.auto.setChecked(True)
        self.auto.toggled.connect(self.enforcer.set_active)
        refresh = QPushButton("Actualizar ventanas")
        refresh.clicked.connect(self.refresh_windows)
        h.addWidget(self.auto)
        h.addWidget(refresh)
        root.addWidget(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Aplicación", "Ventana", "Monitor", "Tamaño"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.window_selected)
        root.addWidget(self.table, 1)

        editor = Card("Nueva regla", "Seleccioná una ventana y definí su zona objetivo.")
        grid = QGridLayout()
        self.selection = QLabel("Ninguna ventana seleccionada")
        self.selection.setStyleSheet("font-weight: 700;")
        grid.addWidget(self.selection, 0, 0, 1, 6)

        self.monitor_combo = QComboBox()
        self.preset = QComboBox()
        self.preset.addItems(list(self.PRESETS))
        self.preset.currentTextChanged.connect(self.apply_preset)
        self.title_filter = QLineEdit()
        self.title_filter.setPlaceholderText("Filtro de título opcional")

        self.x = self._pct_spin(-100, 100, 0)
        self.y = self._pct_spin(-100, 100, 0)
        self.w = self._pct_spin(5, 200, 50)
        self.h = self._pct_spin(5, 200, 100)

        grid.addWidget(QLabel("Monitor"), 1, 0)
        grid.addWidget(self.monitor_combo, 1, 1)
        grid.addWidget(QLabel("Zona"), 1, 2)
        grid.addWidget(self.preset, 1, 3)
        grid.addWidget(QLabel("Título contiene"), 1, 4)
        grid.addWidget(self.title_filter, 1, 5)
        grid.addWidget(QLabel("X %"), 2, 0)
        grid.addWidget(self.x, 2, 1)
        grid.addWidget(QLabel("Y %"), 2, 2)
        grid.addWidget(self.y, 2, 3)
        grid.addWidget(QLabel("Ancho %"), 2, 4)
        grid.addWidget(self.w, 2, 5)
        grid.addWidget(QLabel("Alto %"), 3, 0)
        grid.addWidget(self.h, 3, 1)

        capture = QPushButton("Capturar posición actual")
        capture.clicked.connect(self.capture_position)
        save = primary_button("Guardar regla")
        save.clicked.connect(self.save_rule)
        grid.addWidget(capture, 3, 4)
        grid.addWidget(save, 3, 5)
        editor.body.addLayout(grid)
        root.addWidget(editor)

        saved = Card("Reglas guardadas")
        self.rules_table = QTableWidget(0, 6)
        self.rules_table.setHorizontalHeaderLabels(
            ["Activa", "Aplicación", "Filtro", "Monitor", "Zona", ""]
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
        saved.body.addWidget(self.rules_table)
        root.addWidget(saved)

        self.store.changed.connect(self.refresh_rules)
        self.enforcer.status_changed.connect(
            lambda text: self.status.emit(text)
        )
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
                f"{monitor_display_name(monitor)} · {monitor.width}×{monitor.height}",
                monitor.device,
            )
        if current:
            idx = self.monitor_combo.findData(current)
            if idx >= 0:
                self.monitor_combo.setCurrentIndex(idx)

    def refresh_windows(self) -> None:
        self.refresh_monitors()
        self.windows = enum_windows()
        names = {m.device: m.name for m in self.monitors}
        self.table.setRowCount(len(self.windows))
        for row, window in enumerate(self.windows):
            self.table.setItem(row, 0, QTableWidgetItem(window.process_name))
            self.table.setItem(row, 1, QTableWidgetItem(window.title))
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(names.get(window.monitor_device, window.monitor_device)),
            )
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(f"{window.width}×{window.height}"),
            )
        self.status.emit(f"{len(self.windows)} ventana(s) detectada(s).")

    def window_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.current_window = None
            return
        row = rows[0].row()
        if not (0 <= row < len(self.windows)):
            return
        self.current_window = self.windows[row]
        self.selection.setText(
            f"{self.current_window.process_name} — {self.current_window.title}"
        )
        idx = self.monitor_combo.findData(self.current_window.monitor_device)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)
        self.capture_position()

    def capture_position(self) -> None:
        window = self.current_window
        if window is None:
            return
        monitor = next(
            (m for m in self.monitors if m.device == window.monitor_device),
            None,
        )
        if monitor is None:
            return
        idx = self.monitor_combo.findData(monitor.device)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)
        self.x.setValue((window.left - monitor.work_left) * 100 / monitor.work_width)
        self.y.setValue((window.top - monitor.work_top) * 100 / monitor.work_height)
        self.w.setValue(window.width * 100 / monitor.work_width)
        self.h.setValue(window.height * 100 / monitor.work_height)
        self.preset.setCurrentText("Personalizado")

    def apply_preset(self, name: str) -> None:
        values = self.PRESETS.get(name)
        if values is None:
            return
        x, y, w, h = values
        self.x.setValue(x)
        self.y.setValue(y)
        self.w.setValue(w)
        self.h.setValue(h)

    def save_rule(self) -> None:
        if self.current_window is None:
            QMessageBox.information(
                self,
                "Seleccioná una ventana",
                "Elegí primero una aplicación de la lista superior.",
            )
            return
        device = self.monitor_combo.currentData()
        monitor = next((m for m in self.monitors if m.device == device), None)
        if monitor is None:
            return
        self.store.add_from_window(
            self.current_window,
            monitor,
            title_contains=self.title_filter.text(),
            x_pct=self.x.value(),
            y_pct=self.y.value(),
            width_pct=self.w.value(),
            height_pct=self.h.value(),
        )
        self.enforcer.enforce_once()
        self.status.emit(f"Regla guardada para {self.current_window.process_name}.")

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
            display_names = {
                monitor.device: monitor_display_name(monitor)
                for monitor in enum_monitors()
            }
            self.rules_table.setItem(
                row,
                3,
                QTableWidgetItem(display_names.get(rule.monitor_device, rule.monitor_name)),
            )
            self.rules_table.setItem(
                row,
                4,
                QTableWidgetItem(
                    f"{rule.x_pct:.0f},{rule.y_pct:.0f} · "
                    f"{rule.width_pct:.0f}×{rule.height_pct:.0f}%"
                ),
            )
            remove = danger_button("Eliminar")
            remove.clicked.connect(partial(self.store.remove, rule.id))
            self.rules_table.setCellWidget(row, 5, remove)


class UpdatesPage(QWidget):
    check_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)

        header, _ = _page_header(
            "Actualizaciones",
            "Pantallas descarga e instala versiones nuevas de forma automática y verificada.",
        )
        root.addWidget(header)

        card = Card("Versión instalada")
        version = f"v{__version__}"
        if BUILD_ID:
            version += f" · build {BUILD_ID}"
        self.version = QLabel(version)
        self.version.setStyleSheet("font-size: 18pt; font-weight: 800;")
        card.body.addWidget(self.version)

        self.status = QLabel("Listo para comprobar.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        card.body.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        card.body.addWidget(self.progress)

        self.button = primary_button("Buscar actualizaciones")
        self.button.clicked.connect(self.check_requested)
        card.body.addWidget(self.button)
        root.addWidget(card)

        safety = Card(
            "Instalación robusta",
            "Las nuevas versiones se instalan como una carpeta de aplicación completa. "
            "Ya no se usa el modo one-file que dependía de carpetas temporales _MEI.",
        )
        root.addWidget(safety)
        root.addStretch()

    def set_checking(self) -> None:
        self.button.setEnabled(False)
        self.button.setText("Buscando…")
        self.status.setText("Consultando la última versión publicada…")
        self.progress.hide()

    def set_downloading(self, percent: int) -> None:
        self.button.setText(f"Descargando {percent}%")
        self.status.setText("Descargando y verificando la actualización…")
        self.progress.show()
        self.progress.setValue(percent)

    def set_message(self, message: str, done: bool = True) -> None:
        self.status.setText(message)
        if done:
            self.button.setEnabled(True)
            self.button.setText("Buscar actualizaciones")
            self.progress.hide()


class SettingsPage(QWidget):
    status = Signal(str)
    preferences_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)
        header, _ = _page_header(
            "Configuración",
            "Elegí cómo se comporta Pantallas en Windows.",
        )
        root.addWidget(header)

        prefs = load_preferences()
        startup = Card("Inicio y bandeja")
        self.start_windows = QCheckBox("Iniciar Pantallas con Windows")
        self.start_windows.setChecked(startup_is_registered())
        self.start_minimized = QCheckBox("Iniciar minimizada en la bandeja")
        self.start_minimized.setChecked(bool(prefs["start_minimized"]))
        self.close_to_tray = QCheckBox("Al cerrar, mantener Pantallas en la bandeja")
        self.close_to_tray.setChecked(bool(prefs["close_to_tray"]))
        startup.body.addWidget(self.start_windows)
        startup.body.addWidget(self.start_minimized)
        startup.body.addWidget(self.close_to_tray)
        root.addWidget(startup)

        updates = Card("Actualizaciones")
        self.auto_updates = QCheckBox("Buscar actualizaciones automáticamente")
        self.auto_updates.setChecked(bool(prefs["auto_updates"]))
        updates.body.addWidget(self.auto_updates)
        note = QLabel(
            "Las descargas se validan con SHA-256 antes de ejecutar el instalador."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        updates.body.addWidget(note)
        root.addWidget(updates)

        self.start_windows.toggled.connect(self._startup_changed)
        self.start_minimized.toggled.connect(self._minimized_changed)
        self.close_to_tray.toggled.connect(
            lambda value: self._save("close_to_tray", value)
        )
        self.auto_updates.toggled.connect(
            lambda value: self._save("auto_updates", value)
        )
        root.addStretch()

    def _startup_changed(self, enabled: bool) -> None:
        ok, message = set_windows_startup(
            enabled,
            start_minimized=self.start_minimized.isChecked(),
        )
        if not ok:
            self.start_windows.blockSignals(True)
            self.start_windows.setChecked(not enabled)
            self.start_windows.blockSignals(False)
        self.status.emit(message)
        self.preferences_changed.emit()

    def _minimized_changed(self, enabled: bool) -> None:
        if self.start_windows.isChecked():
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
            save_preferences(start_minimized=enabled)
        self.status.emit(
            "Inicio minimizado activado."
            if enabled
            else "Pantallas se abrirá visible al iniciar."
        )
        self.preferences_changed.emit()

    def _save(self, key: str, value: bool) -> None:
        save_preferences(**{key: value})
        self.status.emit("Configuración guardada.")
        self.preferences_changed.emit()
