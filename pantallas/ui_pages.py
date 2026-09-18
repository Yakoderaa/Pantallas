from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
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
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .build_info import BUILD_ID
from .brightness_cache import get_cached_brightness, set_cached_brightness
from .models import MonitorInfo, WindowInfo
from .monitor_aliases import (
    display_name_for_device,
    monitor_display_name,
    set_monitor_alias,
)
from .monitor_order import ensure_monitor_order, move_monitor, sort_monitors
from .monitor_state import load_disabled_monitors, reconcile_monitors
from .power_profiles import get_power_preference, set_power_preference
from .preferences import (
    load_preferences,
    save_preferences,
    set_windows_startup,
    startup_is_registered,
)
from .rules import RuleEnforcer, RuleStore
from .ui_theme import Card, StatCard, danger_button, primary_button
from .windows_api import (
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
        all_monitors = enum_monitors()
        disabled = reconcile_monitors(all_monitors)
        monitors = [m for m in all_monitors if m.device not in disabled]
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
    brightness_changed = Signal(str, int)
    move_requested = Signal(str, int)
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
        cached = get_cached_brightness(monitor.device)
        if brightness is None:
            if cached is None:
                self.slider.setEnabled(False)
                self.value.setText("N/D")
                self.slider.setToolTip("Este monitor no expone brillo por DDC/CI.")
            else:
                self.slider.setValue(cached)
                self.value.setText(f"{cached}%")
                self.slider.setToolTip(
                    "Último brillo conocido. DDC/CI puede estar reconectando."
                )
                self.slider.sliderReleased.connect(self._brightness_released)
        else:
            set_cached_brightness(monitor.device, brightness)
            self.slider.setValue(brightness)
            self.value.setText(f"{brightness}%")
            self.slider.sliderReleased.connect(self._brightness_released)

        power_row = QHBoxLayout()
        power_label = QLabel("Método de apagado")
        self.power_method = QComboBox()
        self.power_method.addItem("Automático", "auto")
        self.power_method.addItem("Windows", "windows")
        self.power_method.addItem("DDC/CI", "ddc")
        current_method = get_power_preference(monitor.device)
        index = self.power_method.findData(current_method)
        if index >= 0:
            self.power_method.setCurrentIndex(index)
        self.power_method.setToolTip(
            "Automático aprende qué método funciona mejor para este monitor. "
            "Usá Windows si el monitor se apaga por DDC pero después no despierta."
        )
        self.power_method.currentIndexChanged.connect(self._power_method_changed)
        power_row.addWidget(power_label)
        power_row.addWidget(self.power_method)
        power_row.addStretch()
        self.body.addLayout(power_row)

        actions = QHBoxLayout()
        move_up = QPushButton("Subir")
        move_up.setToolTip("Mover este monitor hacia arriba en la lista.")
        move_up.clicked.connect(
            lambda: self.move_requested.emit(self.monitor.device, -1)
        )
        move_down = QPushButton("Bajar")
        move_down.setToolTip("Mover este monitor hacia abajo en la lista.")
        move_down.clicked.connect(
            lambda: self.move_requested.emit(self.monitor.device, 1)
        )
        rename = QPushButton("Cambiar nombre")
        rename.clicked.connect(self._rename)
        disable = danger_button("Apagar")
        disable.setToolTip(
            "Si es el último monitor activo, Pantallas mostrará la protección configurada."
        )
        disable.clicked.connect(lambda: self.disable_requested.emit(self.monitor.device))
        actions.addWidget(move_up)
        actions.addWidget(move_down)
        actions.addWidget(rename)
        actions.addWidget(disable)
        actions.addStretch()
        self.body.addLayout(actions)

    def _brightness_released(self) -> None:
        value = self.slider.value()
        self.value.setText(f"{value}%")
        self.brightness_changed.emit(self.monitor.device, value)

    def _power_method_changed(self) -> None:
        method = str(self.power_method.currentData() or "auto")
        set_power_preference(self.monitor.device, method)

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
    mark_on_requested = Signal(str)
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
        ensure_monitor_order(all_monitors)
        disabled = reconcile_active_devices({m.device for m in all_monitors})
        monitors = sort_monitors(
            [m for m in all_monitors if m.device not in disabled]
        )
        self.current_monitors = monitors

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
                card.brightness_changed.connect(self._set_brightness)
                card.move_requested.connect(self._move_monitor)
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
                already_on = QPushButton("Ya está encendido")
                already_on.setToolTip(
                    "Usalo si el monitor está físicamente encendido pero Pantallas "
                    "todavía conserva un estado de apagado anterior."
                )
                already_on.clicked.connect(
                    lambda _=False, dev=device: self.mark_on_requested.emit(dev)
                )
                row.addWidget(turn_on)
                row.addWidget(already_on)
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

    def _move_monitor(self, device: str, direction: int) -> None:
        all_monitors = enum_monitors()
        if move_monitor(device, direction, all_monitors):
            self.status.emit("Orden de monitores actualizado.")
            self.refresh()

    def _set_brightness(self, device: str, value: int) -> None:
        monitor = next((m for m in enum_monitors() if m.device == device), None)
        if monitor is None:
            self.status.emit("El monitor ya no está activo.")
            self.refresh()
            return
        if set_monitor_brightness(monitor.handle, value):
            set_cached_brightness(device, value)
            self.status.emit(f"Brillo de {monitor_display_name(monitor)}: {value}%")
        else:
            cached = get_cached_brightness(device)
            self.status.emit(
                f"{monitor_display_name(monitor)} todavía no responde por DDC/CI."
            )
            if cached is not None:
                set_cached_brightness(device, cached)
            QTimer.singleShot(1400, self.refresh)


class MonitorsWorkspacePage(QWidget):
    disable_requested = Signal(str)
    enable_requested = Signal(str)
    mark_on_requested = Signal(str)
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.controls = MonitorsPage()
        root.addWidget(self.controls)

        self.controls.disable_requested.connect(self.disable_requested)
        self.controls.enable_requested.connect(self.enable_requested)
        self.controls.mark_on_requested.connect(self.mark_on_requested)
        self.controls.status.connect(self.status)

    def refresh(self) -> None:
        self.controls.refresh()

    def show_controls(self) -> None:
        self.controls.refresh()


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
        self.auto = QCheckBox("Bloqueo de posiciones")
        self.auto.setChecked(bool(load_preferences().get("position_lock_enabled", True)))
        self.auto.toggled.connect(self._auto_changed)
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
        QTimer.singleShot(
            0,
            lambda: self.enforcer.set_active(
                bool(load_preferences().get("position_lock_enabled", True))
            ),
        )

    def _auto_changed(self, enabled: bool) -> None:
        save_preferences(position_lock_enabled=enabled)
        self.enforcer.set_active(enabled)
        self.status.emit(
            "Bloqueo de posiciones activado."
            if enabled
            else "Bloqueo de posiciones desactivado."
        )

    def set_position_lock_enabled(self, enabled: bool) -> None:
        self.auto.blockSignals(True)
        self.auto.setChecked(bool(enabled))
        self.auto.blockSignals(False)
        save_preferences(position_lock_enabled=bool(enabled))
        self.enforcer.set_active(bool(enabled))

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
        all_monitors = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in all_monitors})
        self.monitors = sort_monitors(
            [m for m in all_monitors if m.device not in disabled]
        )
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

        safety = Card(
            "Seguridad de monitores",
            "Por defecto Pantallas impide apagar la última pantalla activa.",
        )
        self.allow_all_off = QCheckBox("Permitir apagar todos los monitores")
        self.allow_all_off.setChecked(bool(prefs["allow_all_monitors_off"]))
        safety_note = QLabel(
            "Desactivar esta protección puede dejarte sin ninguna pantalla visible. "
            "Para recuperarlas podrías necesitar usar el botón físico del monitor "
            "o reiniciar Windows."
        )
        safety_note.setObjectName("Muted")
        safety_note.setWordWrap(True)
        safety.body.addWidget(self.allow_all_off)
        safety.body.addWidget(safety_note)
        root.addWidget(safety)

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
        self.allow_all_off.toggled.connect(self._allow_all_off_changed)
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

    def _allow_all_off_changed(self, enabled: bool) -> None:
        if enabled:
            answer = QMessageBox.warning(
                self,
                "Advertencia: podrías quedarte sin pantalla",
                "Si permitís apagar todos los monitores, Pantallas ya no podrá "
                "garantizar que quede una pantalla visible para volver a abrirlos.\n\n"
                "Podrías necesitar encender un monitor físicamente o reiniciar Windows.\n\n"
                "¿Querés desactivar igualmente la protección?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.allow_all_off.blockSignals(True)
                self.allow_all_off.setChecked(False)
                self.allow_all_off.blockSignals(False)
                return

        save_preferences(allow_all_monitors_off=enabled)
        self.status.emit(
            "Protección del último monitor desactivada."
            if enabled
            else "Protección del último monitor activada."
        )
        self.preferences_changed.emit()

    def _save(self, key: str, value: bool) -> None:
        save_preferences(**{key: value})
        self.status.emit("Configuración guardada.")
        self.preferences_changed.emit()
