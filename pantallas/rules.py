from __future__ import annotations

import json
import os
import uuid
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .models import MonitorInfo, WindowInfo, WindowRule
from .monitor_state import reconcile_active_devices
from .windows_api import enum_monitors, enum_windows, move_window, window_matches


def rules_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "Pantallas"
    base.mkdir(parents=True, exist_ok=True)
    return base / "rules.json"


class RuleStore(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._rules: list[WindowRule] = []
        self.load()

    @property
    def rules(self) -> list[WindowRule]:
        return list(self._rules)

    def load(self) -> None:
        path = rules_path()
        if not path.exists():
            self._rules = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._rules = [
                WindowRule.from_dict(item)
                for item in raw
                if isinstance(item, dict)
            ]
        except Exception:
            self._rules = []

    def save(self) -> None:
        path = rules_path()
        temp = path.with_suffix(".tmp")
        payload = [rule.to_dict() for rule in self._rules]
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(path)
        self.changed.emit()

    def add_from_window(
        self,
        window: WindowInfo,
        monitor: MonitorInfo,
        *,
        title_contains: str,
        x_pct: float,
        y_pct: float,
        width_pct: float,
        height_pct: float,
    ) -> WindowRule:
        rule = WindowRule(
            id=str(uuid.uuid4()),
            process_name=window.process_name,
            process_path=window.process_path,
            class_name=window.class_name,
            title_contains=title_contains.strip(),
            monitor_device=monitor.device,
            monitor_name=monitor.name,
            x_pct=float(x_pct),
            y_pct=float(y_pct),
            width_pct=float(width_pct),
            height_pct=float(height_pct),
            enabled=True,
        )
        self._rules.append(rule)
        self.save()
        return rule

    def remove(self, rule_id: str) -> None:
        self._rules = [r for r in self._rules if r.id != rule_id]
        self.save()

    def set_enabled(self, rule_id: str, enabled: bool) -> None:
        self._rules = [
            replace(rule, enabled=enabled) if rule.id == rule_id else rule
            for rule in self._rules
        ]
        self.save()


class RuleEnforcer(QObject):
    status_changed = Signal(str)

    def __init__(self, store: RuleStore, interval_ms: int = 1200) -> None:
        super().__init__()
        self.store = store
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.enforce_once)
        self._last_status = ""

    @property
    def active(self) -> bool:
        return self.timer.isActive()

    def set_active(self, active: bool) -> None:
        if active:
            if not self.timer.isActive():
                self.timer.start()
            self.enforce_once()
        else:
            self.timer.stop()
            self._emit_status("Bloqueo automático pausado")

    def _emit_status(self, status: str) -> None:
        if status != self._last_status:
            self._last_status = status
            self.status_changed.emit(status)

    def enforce_once(self) -> None:
        rules = [rule for rule in self.store.rules if rule.enabled]
        if not rules:
            self._emit_status("Sin reglas activas")
            return

        all_monitors = enum_monitors()
        disabled = reconcile_active_devices(
            {monitor.device for monitor in all_monitors}
        )
        monitors = {
            monitor.device: monitor
            for monitor in all_monitors
            if monitor.device not in disabled
        }
        windows = enum_windows()
        moved = 0
        matched = 0

        for rule in rules:
            monitor = monitors.get(rule.monitor_device)
            if monitor is None:
                # Fallback when Windows renumbers DISPLAYn after a reconnect.
                monitor = next(
                    (m for m in monitors.values() if m.name == rule.monitor_name),
                    None,
                )
            if monitor is None:
                continue

            target_x = monitor.work_left + round(monitor.work_width * rule.x_pct / 100)
            target_y = monitor.work_top + round(monitor.work_height * rule.y_pct / 100)
            target_w = round(monitor.work_width * rule.width_pct / 100)
            target_h = round(monitor.work_height * rule.height_pct / 100)

            for window in windows:
                if not window_matches(
                    window,
                    process_name=rule.process_name,
                    process_path=rule.process_path,
                    class_name=rule.class_name,
                    title_contains=rule.title_contains,
                ):
                    continue
                matched += 1
                tolerance = 4
                if (
                    abs(window.left - target_x) > tolerance
                    or abs(window.top - target_y) > tolerance
                    or abs(window.width - target_w) > tolerance
                    or abs(window.height - target_h) > tolerance
                ):
                    if move_window(window.hwnd, target_x, target_y, target_w, target_h):
                        moved += 1

        if moved:
            self._emit_status(f"{moved} ventana(s) recolocada(s)")
        elif matched:
            self._emit_status("Ventanas bloqueadas en posición")
        else:
            self._emit_status("Esperando aplicaciones de las reglas")
