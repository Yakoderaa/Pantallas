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


def _first_icon(*paths: str) -> QIcon:
    for relative in paths:
        path = resource_path(relative)
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def app_icon() -> QIcon:
    return _first_icon(
        "assets/generated/pantallas-256.png",
        "assets/brand/pantallas.svg",
    )


def tray_icon() -> QIcon:
    return _first_icon(
        "assets/generated/pantallas-tray-256.png",
        "assets/brand/pantallas-tray.svg",
        "assets/generated/pantallas-256.png",
        "assets/brand/pantallas.svg",
    )
