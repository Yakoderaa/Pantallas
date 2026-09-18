from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .models import MonitorInfo
from .windows_api import monitor_ddc_is_awake


def _state_path() -> Path:
    base = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / "disabled_monitors.json"


def _write_state(state: dict[str, dict]) -> None:
    _state_path().write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    _write_state(state)


def remove_disabled_monitor(device: str) -> None:
    state = load_disabled_monitors()
    if device in state:
        state.pop(device, None)
        _write_state(state)


def reconcile_active_devices(
    active_devices: set[str],
    awake_devices: set[str] | None = None,
) -> dict[str, dict]:
    """Reconcile persisted off-state against Windows and confirmed wake state."""
    state = load_disabled_monitors()
    changed = False
    awake_devices = awake_devices or set()

    for device in list(state):
        profile = state.get(device, {})
        mode = str(profile.get("mode", "windows_disabled"))

        if device not in active_devices:
            continue

        # A Windows-disabled monitor reappearing in EnumDisplayMonitors means
        # Windows has restored the display path, so the saved off state is stale.
        if not mode.startswith("ddc_"):
            state.pop(device, None)
            changed = True
            continue

        # DDC sleep states remain in Windows' logical topology. Clear them only
        # when hardware probing confirms the panel is responding as awake again.
        if device in awake_devices:
            state.pop(device, None)
            changed = True

    if changed:
        _write_state(state)
    return state


def reconcile_monitors(monitors: list[MonitorInfo]) -> dict[str, dict]:
    """Reconcile persisted state using actual monitor handles when possible."""
    state = load_disabled_monitors()
    if not state:
        return {}

    by_device = {monitor.device: monitor for monitor in monitors}
    awake: set[str] = set()

    for device, profile in state.items():
        mode = str(profile.get("mode", "windows_disabled"))
        monitor = by_device.get(device)
        if monitor is None or not mode.startswith("ddc_"):
            continue
        try:
            if monitor_ddc_is_awake(monitor.handle):
                awake.add(device)
        except Exception:
            # A failed probe must never flip an off monitor back to active.
            pass

    return reconcile_active_devices(set(by_device), awake)


def marked_off_devices() -> set[str]:
    return set(load_disabled_monitors())
