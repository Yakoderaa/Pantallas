from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / relative


def app_icon() -> QIcon:
    path = resource_path("assets/brand/pantallas.svg")
    return QIcon(str(path)) if path.exists() else QIcon()


def tray_icon() -> QIcon:
    path = resource_path("assets/brand/pantallas-tray.svg")
    return QIcon(str(path)) if path.exists() else app_icon()
