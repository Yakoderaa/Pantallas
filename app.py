from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from pantallas.main_window import MainWindow
from pantallas.resources import app_icon


APP_USER_MODEL_ID = "Yakoderaa.Pantallas"


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception:
        pass


def main() -> int:
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Pantallas")
    app.setOrganizationName("Yakoderaa")
    app.setApplicationDisplayName("Pantallas")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    start_minimized = "--minimized" in sys.argv[1:]

    window = MainWindow()
    if start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
