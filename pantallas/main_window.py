from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .build_info import BUILD_ID
from .monitor_aliases import display_name_for_device, monitor_display_name
from .monitor_state import (
    load_disabled_monitors,
    reconcile_active_devices,
    remove_disabled_monitor,
    save_disabled_monitor,
)
from .preferences import (
    load_preferences,
    set_windows_startup,
    startup_is_registered,
)
from .rules import RuleEnforcer, RuleStore
from .ui_pages import (
    DashboardPage,
    MonitorsWorkspacePage,
    RulesPage,
    SettingsPage,
    UpdatesPage,
)
from .ui_theme import APP_STYLE
from .update_service import UpdateWorker, launch_installer_after_exit
from .windows_api import (
    disable_monitor,
    enable_monitor,
    enum_monitors,
    set_monitor_brightness,
)


class MainWindow(QMainWindow):
    PAGE_ORDER = (
        ("home", "Inicio"),
        ("monitors", "Monitores"),
        ("windows", "Ventanas y reglas"),
        ("updates", "Actualizaciones"),
        ("settings", "Configuración"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pantallas")
        self.resize(1380, 860)
        self.setMinimumSize(1080, 700)
        self.setStyleSheet(APP_STYLE)

        self.store = RuleStore()
        self.enforcer = RuleEnforcer(self.store)

        self._really_quit = False
        self._update_worker: UpdateWorker | None = None
        self._update_manual = False

        self._build_ui()
        self._build_tray()
        self._wire_pages()
        self.refresh_all()

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(30 * 60 * 1000)
        self.update_timer.timeout.connect(
            lambda: self.check_for_updates(manual=False)
        )
        self._sync_update_timer()
        if load_preferences().get("auto_updates", True):
            QTimer.singleShot(
                5000,
                lambda: self.check_for_updates(manual=False),
            )

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 20, 18, 18)
        side.setSpacing(8)

        brand = QLabel("Pantallas")
        brand.setObjectName("Brand")
        brand_sub = QLabel("Control de escritorio")
        brand_sub.setObjectName("BrandSub")
        side.addWidget(brand)
        side.addWidget(brand_sub)
        side.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}

        for index, (key, label) in enumerate(self.PAGE_ORDER):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _=False, page=key: self.navigate(page)
            )
            self.nav_group.addButton(button, index)
            self.nav_buttons[key] = button
            side.addWidget(button)

        side.addStretch()

        build_text = f"v{__version__}"
        if BUILD_ID:
            build_text += f" · build {BUILD_ID}"
        build = QLabel(build_text)
        build.setObjectName("Muted")
        side.addWidget(build)

        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {
            "home": DashboardPage(),
            "monitors": MonitorsWorkspacePage(),
            "windows": RulesPage(self.store, self.enforcer),
            "updates": UpdatesPage(),
            "settings": SettingsPage(),
        }
        for key, _label in self.PAGE_ORDER:
            self.stack.addWidget(self.pages[key])
        root.addWidget(self.stack, 1)

        self.statusBar().showMessage("Listo")
        self.nav_buttons["home"].setChecked(True)
        self.stack.setCurrentWidget(self.pages["home"])

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        icon: QIcon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("Pantallas")

        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.rebuild_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _wire_pages(self) -> None:
        dashboard: DashboardPage = self.pages["home"]
        monitors: MonitorsWorkspacePage = self.pages["monitors"]
        rules: RulesPage = self.pages["windows"]
        updates: UpdatesPage = self.pages["updates"]
        settings: SettingsPage = self.pages["settings"]

        dashboard.navigate.connect(self.navigate)
        dashboard.refresh_requested.connect(self.refresh_all)

        monitors.disable_requested.connect(self.disable_monitor_from_ui)
        monitors.enable_requested.connect(self.enable_monitor_from_ui)
        monitors.status.connect(self._status)

        rules.status.connect(self._status)

        updates.check_requested.connect(
            lambda: self.check_for_updates(manual=True)
        )

        settings.status.connect(self._status)
        settings.preferences_changed.connect(self._settings_changed)

    def navigate(self, page: str) -> None:
        if page == "monitor-layout":
            widget = self.pages["monitors"]
            self.stack.setCurrentWidget(widget)
            self.nav_buttons["monitors"].setChecked(True)
            workspace: MonitorsWorkspacePage = self.pages["monitors"]
            workspace.show_layout()
            return

        widget = self.pages.get(page)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        button = self.nav_buttons.get(page)
        if button:
            button.setChecked(True)

        if page == "home":
            self.pages["home"].refresh_view(self.store)
        elif page == "monitors":
            workspace: MonitorsWorkspacePage = self.pages["monitors"]
            workspace.show_controls()
        elif page == "windows":
            self.pages["windows"].refresh_windows()

    def refresh_all(self) -> None:
        self.pages["home"].refresh_view(self.store)
        self.pages["monitors"].refresh()
        self.pages["windows"].refresh_monitors()

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message, 7000)

    def _settings_changed(self) -> None:
        self._sync_update_timer()
        self.pages["home"].refresh_view(self.store)

    def _sync_update_timer(self) -> None:
        enabled = bool(load_preferences().get("auto_updates", True))
        if enabled and not self.update_timer.isActive():
            self.update_timer.start()
        elif not enabled and self.update_timer.isActive():
            self.update_timer.stop()

    def _move_window_to_monitor(self, device: str) -> None:
        monitor = next(
            (m for m in enum_monitors() if m.device == device),
            None,
        )
        if monitor is None:
            return
        width = min(
            max(self.width(), self.minimumWidth()),
            max(760, monitor.work_width - 80),
        )
        height = min(
            max(self.height(), self.minimumHeight()),
            max(560, monitor.work_height - 80),
        )
        self.showNormal()
        self.resize(width, height)
        self.move(monitor.work_left + 40, monitor.work_top + 40)
        QApplication.processEvents()

    def open_monitor_config(self, device: str) -> None:
        self.stack.setCurrentWidget(self.pages["monitors"])
        self.nav_buttons["monitors"].setChecked(True)
        workspace: MonitorsWorkspacePage = self.pages["monitors"]
        workspace.show_layout_for(device)

    def _effective_active_monitors(self):
        all_monitors = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in all_monitors})
        return [m for m in all_monitors if m.device not in disabled]

    def disable_monitor_from_ui(self, device: str) -> None:
        active = self._effective_active_monitors()
        target = next((m for m in active if m.device == device), None)
        if target is None:
            self._status("La pantalla seleccionada ya no está activa.")
            self.refresh_all()
            return

        alternatives = [m for m in active if m.device != device]
        if not alternatives:
            QMessageBox.information(
                self,
                "Última pantalla activa",
                "Pantallas no permite apagar la última pantalla activa.",
            )
            return

        if self.isVisible():
            self._move_window_to_monitor(alternatives[0].device)

        ok, message, profile = disable_monitor(device)
        if not ok or profile is None:
            QMessageBox.warning(self, "No se pudo apagar", message)
            return

        profile["name"] = monitor_display_name(target)
        save_disabled_monitor(profile)
        self._status(message)
        self.tray.showMessage(
            "Monitor apagado",
            f"{monitor_display_name(target)} quedó apagado. Podés encenderlo desde Pantallas o la bandeja.",
            QSystemTrayIcon.MessageIcon.Information,
            3500,
        )
        QTimer.singleShot(900, self.refresh_all)

    def enable_monitor_from_ui(self, device: str) -> None:
        profile = load_disabled_monitors().get(device)
        if profile is None:
            self._status("No se encontró el perfil guardado de ese monitor.")
            self.refresh_all()
            return

        ok, message = enable_monitor(profile)
        if not ok:
            QMessageBox.warning(self, "No se pudo encender", message)
            return

        remove_disabled_monitor(device)
        self._status(message)
        QTimer.singleShot(1200, self.refresh_all)

    def set_tray_brightness(self, device: str, percent: int) -> None:
        monitor = next(
            (m for m in enum_monitors() if m.device == device),
            None,
        )
        if monitor is None:
            self.tray.showMessage(
                "Pantallas",
                "Ese monitor ya no está activo.",
            )
            return

        if set_monitor_brightness(monitor.handle, percent):
            self._status(f"Brillo de {monitor_display_name(monitor)}: {percent}%")
            if self.stack.currentWidget() is self.pages["monitors"]:
                workspace: MonitorsWorkspacePage = self.pages["monitors"]
                workspace.controls.refresh()
        else:
            self.tray.showMessage(
                "Brillo no disponible",
                f"{monitor_display_name(monitor)} no aceptó el cambio por DDC/CI.",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )

    def rebuild_tray_menu(self) -> None:
        self.tray_menu.clear()

        open_action = self.tray_menu.addAction("Abrir Pantallas")
        open_action.triggered.connect(self.show_from_tray)
        self.tray_menu.addSeparator()

        all_monitors = enum_monitors()
        disabled = reconcile_active_devices({m.device for m in all_monitors})
        active = [m for m in all_monitors if m.device not in disabled]

        for monitor in active:
            label = monitor_display_name(monitor)
            if monitor.primary:
                label += " · principal"
            submenu = self.tray_menu.addMenu(label)

            configure = submenu.addAction("Abrir y configurar")
            configure.triggered.connect(
                lambda _=False, dev=monitor.device: self._open_monitor_from_tray(dev)
            )

            brightness = submenu.addMenu("Brillo")
            for value in (25, 50, 75, 100):
                action = brightness.addAction(f"{value}%")
                action.triggered.connect(
                    lambda _=False, dev=monitor.device, pct=value:
                        self.set_tray_brightness(dev, pct)
                )

            submenu.addSeparator()
            off = submenu.addAction("Apagar monitor")
            off.setEnabled(len(active) > 1)
            off.triggered.connect(
                lambda _=False, dev=monitor.device:
                    self.disable_monitor_from_ui(dev)
            )

        for device, profile in disabled.items():
            submenu = self.tray_menu.addMenu(
                f"{display_name_for_device(device, str(profile.get('name', device)))} · apagado"
            )
            on = submenu.addAction("Encender monitor")
            on.triggered.connect(
                lambda _=False, dev=device:
                    self.enable_monitor_from_ui(dev)
            )

        self.tray_menu.addSeparator()

        startup = self.tray_menu.addAction("Iniciar con Windows")
        startup.setCheckable(True)
        startup.setChecked(startup_is_registered())
        startup.toggled.connect(self._tray_toggle_startup)

        prefs = load_preferences()
        minimized = self.tray_menu.addAction("Iniciar minimizada")
        minimized.setCheckable(True)
        minimized.setChecked(bool(prefs.get("start_minimized", True)))
        minimized.toggled.connect(self._tray_toggle_minimized)

        self.tray_menu.addSeparator()

        update = self.tray_menu.addAction("Buscar actualizaciones")
        update.triggered.connect(
            lambda: self.check_for_updates(manual=True)
        )

        quit_action = self.tray_menu.addAction("Salir")
        quit_action.triggered.connect(self.quit_app)

    def _tray_toggle_startup(self, enabled: bool) -> None:
        prefs = load_preferences()
        ok, message = set_windows_startup(
            enabled,
            start_minimized=bool(prefs.get("start_minimized", True)),
        )
        self._status(message)
        if ok:
            settings: SettingsPage = self.pages["settings"]
            settings.start_windows.blockSignals(True)
            settings.start_windows.setChecked(enabled)
            settings.start_windows.blockSignals(False)
            self.pages["home"].refresh_view(self.store)

    def _tray_toggle_minimized(self, enabled: bool) -> None:
        settings: SettingsPage = self.pages["settings"]
        settings.start_minimized.setChecked(enabled)

    def _open_monitor_from_tray(self, device: str) -> None:
        self.show_from_tray()
        self._move_window_to_monitor(device)
        self.open_monitor_config(device)

    def check_for_updates(self, manual: bool = False) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            if manual:
                self._status("Ya hay una comprobación en curso.")
            return

        self._update_manual = manual
        page: UpdatesPage = self.pages["updates"]
        page.set_checking()

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
        self._status(message)
        self.pages["updates"].status.setText(message)

    def _update_progress(self, percent: int) -> None:
        self.pages["updates"].set_downloading(percent)

    def _no_update_available(self, latest_build: int) -> None:
        message = "Pantallas ya está actualizado."
        if BUILD_ID:
            message += f" Build actual: {BUILD_ID}."
        self.pages["updates"].set_message(message)
        self._status(message)
        if self._update_manual:
            QMessageBox.information(self, "Sin actualizaciones", message)

    def _update_failed(self, message: str) -> None:
        full = f"No se pudo actualizar: {message}"
        self.pages["updates"].set_message(full)
        self._status(full)
        if self._update_manual:
            QMessageBox.warning(self, "Actualización", full)

    def _installer_ready(self, installer_path: str, latest_build: int) -> None:
        message = (
            f"Build {latest_build} descargado y verificado. "
            "Pantallas se cerrará para instalarlo."
        )
        self.pages["updates"].set_message(message, done=False)
        self._status(message)

        if not launch_installer_after_exit(installer_path):
            self._update_failed("No se pudo iniciar el instalador descargado.")
            return

        self._really_quit = True
        self.enforcer.set_active(False)
        self.update_timer.stop()
        self.tray.hide()
        QApplication.instance().quit()

    def _update_finished(self) -> None:
        worker = self._update_worker
        self._update_worker = None
        if worker is not None:
            worker.deleteLater()

        page: UpdatesPage = self.pages["updates"]
        if not page.button.isEnabled():
            page.button.setEnabled(True)
            page.button.setText("Buscar actualizaciones")

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def quit_app(self) -> None:
        self._really_quit = True
        self.enforcer.set_active(False)
        self.update_timer.stop()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._really_quit:
            event.accept()
            return

        prefs = load_preferences()
        close_to_tray = bool(prefs.get("close_to_tray", True))
        if close_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Pantallas sigue activo",
                "Los controles y reglas siguen disponibles desde la bandeja.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return

        self.quit_app()
        event.accept()
