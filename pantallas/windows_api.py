from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Iterable

import psutil
import win32api
import win32con
import win32gui
import win32process

from .models import MonitorInfo, WindowInfo


# ChangeDisplaySettingsEx flags / DEVMODE fields.
_CDS_UPDATEREGISTRY = getattr(win32con, "CDS_UPDATEREGISTRY", 0x00000001)
_CDS_NORESET = getattr(win32con, "CDS_NORESET", 0x10000000)
_DM_POSITION = getattr(win32con, "DM_POSITION", 0x00000020)
_DM_DISPLAYORIENTATION = getattr(win32con, "DM_DISPLAYORIENTATION", 0x00000080)
_DM_PELSWIDTH = getattr(win32con, "DM_PELSWIDTH", 0x00080000)
_DM_PELSHEIGHT = getattr(win32con, "DM_PELSHEIGHT", 0x00100000)

_ORIENTATION_TO_WIN32 = {
    0: getattr(win32con, "DMDO_DEFAULT", 0),
    90: getattr(win32con, "DMDO_90", 1),
    180: getattr(win32con, "DMDO_180", 2),
    270: getattr(win32con, "DMDO_270", 3),
}
_WIN32_TO_ORIENTATION = {value: key for key, value in _ORIENTATION_TO_WIN32.items()}


class _PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


_dxva2 = ctypes.WinDLL("Dxva2.dll")
_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
]
_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL

_dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(_PHYSICAL_MONITOR),
]
_dxva2.GetPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL

_dxva2.DestroyPhysicalMonitors.argtypes = [
    wintypes.DWORD,
    ctypes.POINTER(_PHYSICAL_MONITOR),
]
_dxva2.DestroyPhysicalMonitors.restype = wintypes.BOOL

_dxva2.GetMonitorBrightness.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_dxva2.GetMonitorBrightness.restype = wintypes.BOOL

_dxva2.SetMonitorBrightness.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_dxva2.SetMonitorBrightness.restype = wintypes.BOOL

_dxva2.SetVCPFeature.argtypes = [
    wintypes.HANDLE,
    wintypes.BYTE,
    wintypes.DWORD,
]
_dxva2.SetVCPFeature.restype = wintypes.BOOL


def _handle_value(handle: object) -> int:
    try:
        return int(handle)
    except TypeError:
        return int(handle.handle)


def _friendly_monitor_name(device: str) -> str:
    try:
        display = win32api.EnumDisplayDevices(device, 0)
        name = getattr(display, "DeviceString", "") or ""
        if name.strip():
            return name.strip()
    except Exception:
        pass
    return device.replace("\\\\.\\", "")


def enum_monitors() -> list[MonitorInfo]:
    monitors: list[MonitorInfo] = []
    for hmonitor, _hdc, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(hmonitor)
        left, top, right, bottom = info["Monitor"]
        wleft, wtop, wright, wbottom = info["Work"]
        device = str(info["Device"])
        primary = bool(info["Flags"] & getattr(win32con, "MONITORINFOF_PRIMARY", 1))
        orientation = 0
        try:
            devmode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)
            orientation = _WIN32_TO_ORIENTATION.get(int(devmode.DisplayOrientation), 0)
        except Exception:
            orientation = 0

        monitors.append(
            MonitorInfo(
                handle=_handle_value(hmonitor),
                device=device,
                name=_friendly_monitor_name(device),
                left=int(left),
                top=int(top),
                right=int(right),
                bottom=int(bottom),
                work_left=int(wleft),
                work_top=int(wtop),
                work_right=int(wright),
                work_bottom=int(wbottom),
                orientation=orientation,
                primary=primary,
            )
        )

    monitors.sort(key=lambda m: (0 if m.primary else 1, m.left, m.top))
    return monitors


def apply_monitor_layout(layout: Iterable[dict[str, int | str]]) -> tuple[bool, str]:
    """Apply monitor x/y/orientation with CDS_NORESET then commit all at once."""
    staged: list[str] = []
    try:
        for item in layout:
            device = str(item["device"])
            x = int(item["x"])
            y = int(item["y"])
            orientation_deg = int(item["orientation"])
            target_orientation = _ORIENTATION_TO_WIN32.get(orientation_deg)
            if target_orientation is None:
                return False, f"Orientación no válida: {orientation_deg}"

            devmode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)
            current_orientation = int(devmode.DisplayOrientation)

            devmode.Position_x = x
            devmode.Position_y = y
            devmode.Fields |= _DM_POSITION

            if current_orientation != target_orientation:
                # Windows expects width/height swapped when crossing portrait/landscape.
                if (current_orientation % 2) != (target_orientation % 2):
                    devmode.PelsWidth, devmode.PelsHeight = devmode.PelsHeight, devmode.PelsWidth
                devmode.DisplayOrientation = target_orientation
                devmode.Fields |= _DM_DISPLAYORIENTATION | _DM_PELSWIDTH | _DM_PELSHEIGHT

            # pywin32 exposes the 3-argument wrapper: DeviceName, DevMode, Flags.
            result = win32api.ChangeDisplaySettingsEx(
                device,
                devmode,
                _CDS_UPDATEREGISTRY | _CDS_NORESET,
            )
            if result != win32con.DISP_CHANGE_SUCCESSFUL:
                return False, f"Windows rechazó {device} (código {result})."
            staged.append(device)

        # Passing a NULL DEVMODE commits all staged CDS_NORESET changes.
        result = win32api.ChangeDisplaySettingsEx(None, None, 0)
        if result != win32con.DISP_CHANGE_SUCCESSFUL:
            return False, f"No se pudo aplicar la distribución final (código {result})."
        return True, f"Distribución aplicada en {len(staged)} pantalla(s)."
    except Exception as exc:
        return False, f"No se pudo aplicar la distribución: {exc}"


def _physical_monitors(hmonitor: int) -> tuple[object | None, int]:
    count = wintypes.DWORD(0)
    hm = wintypes.HANDLE(hmonitor)
    if not _dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hm, ctypes.byref(count)):
        return None, 0
    if count.value == 0:
        return None, 0

    array_type = _PHYSICAL_MONITOR * count.value
    array = array_type()
    if not _dxva2.GetPhysicalMonitorsFromHMONITOR(hm, count, array):
        return None, 0
    return array, int(count.value)


def get_monitor_brightness(hmonitor: int) -> int | None:
    array, count = _physical_monitors(hmonitor)
    if not array or count <= 0:
        return None
    try:
        for physical in array:
            minimum = wintypes.DWORD(0)
            current = wintypes.DWORD(0)
            maximum = wintypes.DWORD(0)
            if _dxva2.GetMonitorBrightness(
                physical.hPhysicalMonitor,
                ctypes.byref(minimum),
                ctypes.byref(current),
                ctypes.byref(maximum),
            ):
                span = max(1, int(maximum.value) - int(minimum.value))
                pct = round((int(current.value) - int(minimum.value)) * 100 / span)
                return max(0, min(100, pct))
        return None
    finally:
        _dxva2.DestroyPhysicalMonitors(count, array)


def set_monitor_brightness(hmonitor: int, percent: int) -> bool:
    percent = max(0, min(100, int(percent)))
    array, count = _physical_monitors(hmonitor)
    if not array or count <= 0:
        return False
    any_success = False
    try:
        for physical in array:
            minimum = wintypes.DWORD(0)
            current = wintypes.DWORD(0)
            maximum = wintypes.DWORD(0)
            if not _dxva2.GetMonitorBrightness(
                physical.hPhysicalMonitor,
                ctypes.byref(minimum),
                ctypes.byref(current),
                ctypes.byref(maximum),
            ):
                continue
            target = int(minimum.value + (maximum.value - minimum.value) * percent / 100)
            if _dxva2.SetMonitorBrightness(physical.hPhysicalMonitor, target):
                any_success = True
        return any_success
    finally:
        _dxva2.DestroyPhysicalMonitors(count, array)


def set_monitor_power(hmonitor: int, on: bool) -> bool:
    """DDC/CI VCP code 0xD6: 0x01 on, 0x04 soft-off."""
    array, count = _physical_monitors(hmonitor)
    if not array or count <= 0:
        return False
    any_success = False
    value = 0x01 if on else 0x04
    try:
        for physical in array:
            if _dxva2.SetVCPFeature(physical.hPhysicalMonitor, 0xD6, value):
                any_success = True
        return any_success
    finally:
        _dxva2.DestroyPhysicalMonitors(count, array)


def enum_windows() -> list[WindowInfo]:
    windows: list[WindowInfo] = []
    seen: set[int] = set()

    def callback(hwnd: int, _extra: object) -> bool:
        try:
            if hwnd in seen or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd).strip()
            if not title:
                return True

            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right - left < 40 or bottom - top < 40:
                return True

            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return True
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
                process_path = proc.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                process_name = f"PID {pid}"
                process_path = ""

            class_name = win32gui.GetClassName(hwnd)
            hmonitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            monitor_info = win32api.GetMonitorInfo(hmonitor)
            monitor_device = str(monitor_info["Device"])

            seen.add(hwnd)
            windows.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    title=title,
                    process_name=process_name,
                    process_path=process_path,
                    class_name=class_name,
                    left=int(left),
                    top=int(top),
                    right=int(right),
                    bottom=int(bottom),
                    monitor_device=monitor_device,
                )
            )
        except Exception:
            return True
        return True

    win32gui.EnumWindows(callback, None)
    windows.sort(key=lambda w: (w.process_name.lower(), w.title.lower()))
    return windows


def move_window(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    try:
        if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
            return False
        flags = (
            getattr(win32con, "SWP_NOACTIVATE", 0x0010)
            | getattr(win32con, "SWP_NOZORDER", 0x0004)
            | getattr(win32con, "SWP_ASYNCWINDOWPOS", 0x4000)
        )
        win32gui.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            max(100, int(width)),
            max(100, int(height)),
            flags,
        )
        return True
    except Exception:
        return False


def window_matches(
    window: WindowInfo,
    *,
    process_name: str,
    process_path: str,
    class_name: str,
    title_contains: str,
) -> bool:
    if process_name and window.process_name.lower() != process_name.lower():
        return False
    if process_path:
        try:
            if Path(window.process_path).resolve() != Path(process_path).resolve():
                return False
        except Exception:
            if window.process_path.lower() != process_path.lower():
                return False
    if class_name and window.class_name != class_name:
        return False
    if title_contains and title_contains.lower() not in window.title.lower():
        return False
    return True
