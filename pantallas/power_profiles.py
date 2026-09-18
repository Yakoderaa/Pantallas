from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QStandardPaths


PowerPreference = Literal["auto", "windows", "ddc"]


def _path() -> Path:
    base = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / "monitor_power_profiles.json"


def _load() -> dict[str, dict]:
    path = _path()
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


def _save(data: dict[str, dict]) -> None:
    _path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_power_profile(device: str) -> dict:
    data = _load()
    profile = dict(data.get(device, {}))
    profile.setdefault("preference", "auto")
    profile.setdefault("ddc_off_successes", 0)
    profile.setdefault("ddc_off_failures", 0)
    profile.setdefault("ddc_wake_successes", 0)
    profile.setdefault("ddc_wake_failures", 0)
    profile.setdefault("windows_successes", 0)
    profile.setdefault("windows_failures", 0)
    profile.setdefault("last_method", "")
    return profile


def get_power_preference(device: str) -> PowerPreference:
    value = str(get_power_profile(device).get("preference", "auto"))
    return value if value in {"auto", "windows", "ddc"} else "auto"


def set_power_preference(device: str, preference: str) -> None:
    if preference not in {"auto", "windows", "ddc"}:
        preference = "auto"
    data = _load()
    profile = dict(data.get(device, {}))
    profile["preference"] = preference
    data[device] = profile
    _save(data)


def _record(device: str, key: str, method: str) -> None:
    data = _load()
    profile = dict(data.get(device, {}))
    profile[key] = int(profile.get(key, 0)) + 1
    profile["last_method"] = method
    data[device] = profile
    _save(data)


def record_ddc_off(device: str, success: bool) -> None:
    _record(
        device,
        "ddc_off_successes" if success else "ddc_off_failures",
        "ddc",
    )


def record_ddc_wake(device: str, success: bool) -> None:
    _record(
        device,
        "ddc_wake_successes" if success else "ddc_wake_failures",
        "ddc",
    )


def record_windows_off(device: str, success: bool) -> None:
    _record(
        device,
        "windows_successes" if success else "windows_failures",
        "windows",
    )


def choose_automatic_method(device: str) -> Literal["windows", "ddc"]:
    profile = get_power_profile(device)

    # A single failed DDC wake is enough to avoid putting that panel back
    # into a state from which software cannot recover it.
    if int(profile.get("ddc_wake_failures", 0)) > 0:
        return "windows"

    # If DDC has already proven it cannot turn this panel off, use Windows.
    if int(profile.get("ddc_off_failures", 0)) > 0:
        return "windows"

    # Proven DDC power + wake is the cleanest method because it does not
    # rewrite the Windows desktop topology.
    if (
        int(profile.get("ddc_off_successes", 0)) > 0
        and int(profile.get("ddc_wake_successes", 0)) > 0
    ):
        return "ddc"

    # Start with DDC, but verify the result before accepting it.
    return "ddc"
