from __future__ import annotations

import json
import sys
import winreg
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Pantallas"

DEFAULTS: dict[str, bool] = {
    "start_with_windows": False,
    "start_minimized": True,
    "close_to_tray": True,
    "auto_updates": True,
}


def _settings_dir() -> Path:
    base = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def _prefs_path() -> Path:
    return _settings_dir() / "preferences.json"


def load_preferences() -> dict[str, bool]:
    prefs = dict(DEFAULTS)
    path = _prefs_path()
    if not path.exists():
        return prefs
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in DEFAULTS:
                if key in raw:
                    prefs[key] = bool(raw[key])
    except Exception:
        pass
    return prefs


def save_preferences(**changes: Any) -> dict[str, bool]:
    prefs = load_preferences()
    for key, value in changes.items():
        if key in DEFAULTS:
            prefs[key] = bool(value)
    _prefs_path().write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return prefs


def _startup_command(start_minimized: bool) -> str:
    minimized = " --minimized" if start_minimized else ""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"{minimized}'

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{app_path}"{minimized}'


def set_windows_startup(
    enabled: bool,
    *,
    start_minimized: bool,
) -> tuple[bool, str]:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key,
                    RUN_VALUE,
                    0,
                    winreg.REG_SZ,
                    _startup_command(start_minimized),
                )
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass

        save_preferences(
            start_with_windows=enabled,
            start_minimized=start_minimized,
        )
        return True, (
            "Pantallas se iniciará con Windows."
            if enabled
            else "Pantallas ya no se iniciará con Windows."
        )
    except OSError as exc:
        return False, f"No se pudo cambiar el inicio con Windows: {exc}"


def startup_is_registered() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_QUERY_VALUE,
        ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return bool(str(value).strip())
    except OSError:
        return False
