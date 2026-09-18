from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from pantallas.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pantallas")
    app.setOrganizationName("Yakoderaa")
    app.setQuitOnLastWindowClosed(False)

    start_minimized = "--minimized" in sys.argv[1:]

    window = MainWindow()
    if start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
