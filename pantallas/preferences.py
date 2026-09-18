from __future__ import annotations

import json
import sys
import winreg
from pathlib import Path

from PySide6.QtCore import QStandardPaths


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Pantallas"


def _settings_dir() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _prefs_path() -> Path:
    return _settings_dir() / "preferences.json"


def load_preferences() -> dict[str, bool]:
    defaults = {
        "start_with_windows": False,
        "start_minimized": True,
    }
    path = _prefs_path()
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            defaults["start_with_windows"] = bool(raw.get("start_with_windows", False))
            defaults["start_minimized"] = bool(raw.get("start_minimized", True))
    except Exception:
        pass
    return defaults


def save_preferences(*, start_with_windows: bool, start_minimized: bool) -> None:
    _prefs_path().write_text(
        json.dumps(
            {
                "start_with_windows": bool(start_with_windows),
                "start_minimized": bool(start_minimized),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _startup_command(start_minimized: bool) -> str:
    minimized = " --minimized" if start_minimized else ""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"{minimized}'

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{app_path}"{minimized}'


def set_windows_startup(enabled: bool, *, start_minimized: bool) -> tuple[bool, str]:
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
