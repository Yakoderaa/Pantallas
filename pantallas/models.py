from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class MonitorInfo:
    handle: int
    device: str
    name: str
    left: int
    top: int
    right: int
    bottom: int
    work_left: int
    work_top: int
    work_right: int
    work_bottom: int
    orientation: int
    primary: bool

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def work_width(self) -> int:
        return self.work_right - self.work_left

    @property
    def work_height(self) -> int:
        return self.work_bottom - self.work_top

    @property
    def orientation_label(self) -> str:
        return {
            0: "Horizontal",
            90: "Vertical",
            180: "Horizontal invertida",
            270: "Vertical invertida",
        }.get(self.orientation, f"{self.orientation}°")


@dataclass(slots=True)
class WindowInfo:
    hwnd: int
    title: str
    process_name: str
    process_path: str
    class_name: str
    left: int
    top: int
    right: int
    bottom: int
    monitor_device: str

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(slots=True)
class WindowRule:
    id: str
    process_name: str
    process_path: str
    class_name: str
    title_contains: str
    monitor_device: str
    monitor_name: str
    x_pct: float
    y_pct: float
    width_pct: float
    height_pct: float
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WindowRule":
        return cls(
            id=str(raw["id"]),
            process_name=str(raw.get("process_name", "")),
            process_path=str(raw.get("process_path", "")),
            class_name=str(raw.get("class_name", "")),
            title_contains=str(raw.get("title_contains", "")),
            monitor_device=str(raw.get("monitor_device", "")),
            monitor_name=str(raw.get("monitor_name", "")),
            x_pct=float(raw.get("x_pct", 0.0)),
            y_pct=float(raw.get("y_pct", 0.0)),
            width_pct=float(raw.get("width_pct", 50.0)),
            height_pct=float(raw.get("height_pct", 50.0)),
            enabled=bool(raw.get("enabled", True)),
        )
