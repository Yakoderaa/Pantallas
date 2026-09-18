from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .models import MonitorInfo


def _path() -> Path:
    base = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / "monitor_names.json"


def load_monitor_aliases() -> dict[str, str]:
    path = _path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {
                str(key): str(value).strip()
                for key, value in raw.items()
                if str(value).strip()
            }
    except Exception:
        pass
    return {}


def set_monitor_alias(device: str, alias: str) -> None:
    aliases = load_monitor_aliases()
    alias = alias.strip()
    if alias:
        aliases[device] = alias
    else:
        aliases.pop(device, None)
    _path().write_text(
        json.dumps(aliases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def monitor_display_name(monitor: MonitorInfo) -> str:
    return load_monitor_aliases().get(monitor.device, monitor.name)


def display_name_for_device(device: str, fallback: str = "") -> str:
    aliases = load_monitor_aliases()
    return aliases.get(device, fallback or device)
