from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def _state_path() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base / "disabled_monitors.json"


def load_disabled_monitors() -> dict[str, dict]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {
                str(device): profile
                for device, profile in raw.items()
                if isinstance(profile, dict)
            }
    except Exception:
        pass
    return {}


def save_disabled_monitor(profile: dict) -> None:
    device = str(profile.get("device", ""))
    if not device:
        return
    state = load_disabled_monitors()
    state[device] = profile
    _state_path().write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def remove_disabled_monitor(device: str) -> None:
    state = load_disabled_monitors()
    if device in state:
        state.pop(device, None)
        _state_path().write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def reconcile_active_devices(active_devices: set[str]) -> dict[str, dict]:
    state = load_disabled_monitors()
    changed = False
    for device in list(state):
        if device in active_devices:
            state.pop(device, None)
            changed = True
    if changed:
        _state_path().write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return state
