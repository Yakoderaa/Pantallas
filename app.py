from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pantallas.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pantallas")
    app.setOrganizationName("Yakoderaa")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
