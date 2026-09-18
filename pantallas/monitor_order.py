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
    return base / "monitor_order.json"


def load_monitor_order() -> list[str]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
    except Exception:
        pass
    return []


def save_monitor_order(devices: list[str]) -> None:
    unique: list[str] = []
    for device in devices:
        device = str(device)
        if device and device not in unique:
            unique.append(device)
    _path().write_text(
        json.dumps(unique, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sort_monitors(monitors: list[MonitorInfo]) -> list[MonitorInfo]:
    order = load_monitor_order()
    rank = {device: index for index, device in enumerate(order)}
    return sorted(
        monitors,
        key=lambda monitor: (
            rank.get(monitor.device, len(order) + 1000),
            0 if monitor.primary else 1,
            monitor.left,
            monitor.top,
        ),
    )


def ensure_monitor_order(monitors: list[MonitorInfo]) -> list[str]:
    current = load_monitor_order()
    devices = [monitor.device for monitor in monitors]
    kept = [device for device in current if device in devices]
    for device in devices:
        if device not in kept:
            kept.append(device)
    if kept != current:
        save_monitor_order(kept)
    return kept


def move_monitor(device: str, direction: int, monitors: list[MonitorInfo]) -> bool:
    order = ensure_monitor_order(monitors)
    if device not in order:
        return False
    index = order.index(device)
    target = index + int(direction)
    if target < 0 or target >= len(order):
        return False
    order[index], order[target] = order[target], order[index]
    save_monitor_order(order)
    return True
