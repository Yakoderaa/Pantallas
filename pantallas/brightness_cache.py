from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def _path() -> Path:
    base = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / "brightness_cache.json"


def load_brightness_cache() -> dict[str, int]:
    path = _path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            result: dict[str, int] = {}
            for device, value in raw.items():
                try:
                    result[str(device)] = max(0, min(100, int(value)))
                except Exception:
                    pass
            return result
    except Exception:
        pass
    return {}


def get_cached_brightness(device: str) -> int | None:
    return load_brightness_cache().get(device)


def set_cached_brightness(device: str, value: int) -> None:
    cache = load_brightness_cache()
    cache[str(device)] = max(0, min(100, int(value)))
    _path().write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
