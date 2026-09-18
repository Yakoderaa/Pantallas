from __future__ import annotations

import ctypes
import time
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
_CDS_RESET = getattr(win32con, "CDS_RESET", 0x40000000)
_DM_POSITION = getattr(win32con, "DM_POSITION", 0x00000020)
_DM_DISPLAYORIENTATION = getattr(win32con, "DM_DISPLAYORIENTATION", 0x00000080)
_DM_BITSPERPEL = getattr(win32con, "DM_BITSPERPEL", 0x00040000)
_DM_PELSWIDTH = getattr(win32con, "DM_PELSWIDTH", 0x00080000)
_DM_PELSHEIGHT = getattr(win32con, "DM_PELSHEIGHT", 0x00100000)
_DM_DISPLAYFREQUENCY = getattr(win32con, "DM_DISPLAYFREQUENCY", 0x00400000)

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

_dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
    wintypes.HANDLE,
    wintypes.BYTE,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_dxva2.GetVCPFeatureAndVCPFeatureReply.restype = wintypes.BOOL


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


def capture_monitor_profile(device: str) -> dict:
    monitor = next((m for m in enum_monitors() if m.device == device), None)
    if monitor is None:
        raise RuntimeError("La pantalla ya no está activa.")

    devmode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)
    brightness = get_monitor_brightness(monitor.handle)
    return {
        "device": monitor.device,
        "name": monitor.name,
        "x": int(monitor.left),
        "y": int(monitor.top),
        "width": int(devmode.PelsWidth),
        "height": int(devmode.PelsHeight),
        "orientation": int(monitor.orientation),
        "bits_per_pel": int(getattr(devmode, "BitsPerPel", 32) or 32),
        "frequency": int(getattr(devmode, "DisplayFrequency", 60) or 60),
        "primary": bool(monitor.primary),
        "brightness": brightness,
    }


def _restore_monitor_profile(profile: dict) -> tuple[bool, str]:
    device = str(profile.get("device", ""))
    if not device:
        return False, "No hay información suficiente para restaurar la pantalla."

    try:
        try:
            devmode = win32api.EnumDisplaySettings(
                device,
                getattr(win32con, "ENUM_REGISTRY_SETTINGS", -2),
            )
        except Exception:
            devmode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)

        devmode.Position_x = int(profile.get("x", 0))
        devmode.Position_y = int(profile.get("y", 0))
        devmode.PelsWidth = max(640, int(profile.get("width", 1920)))
        devmode.PelsHeight = max(480, int(profile.get("height", 1080)))
        devmode.DisplayOrientation = _ORIENTATION_TO_WIN32.get(
            int(profile.get("orientation", 0)),
            _ORIENTATION_TO_WIN32[0],
        )
        devmode.BitsPerPel = int(profile.get("bits_per_pel", 32))
        devmode.DisplayFrequency = int(profile.get("frequency", 60))
        devmode.Fields = (
            _DM_POSITION
            | _DM_PELSWIDTH
            | _DM_PELSHEIGHT
            | _DM_DISPLAYORIENTATION
            | _DM_BITSPERPEL
            | _DM_DISPLAYFREQUENCY
        )

        result = win32api.ChangeDisplaySettingsEx(
            device,
            devmode,
            _CDS_UPDATEREGISTRY,
        )
        if result != win32con.DISP_CHANGE_SUCCESSFUL:
            return False, f"Windows rechazó restaurar {device} (código {result})."
        return True, ""
    except Exception as exc:
        return False, f"No se pudo restaurar la salida: {exc}"


def _wake_windows_displays() -> None:
    # Reset Windows' display idle timer and explicitly request display power-on.
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x00000001 | 0x00000002)
    except Exception:
        pass
    try:
        win32gui.PostMessage(
            win32con.HWND_BROADCAST,
            win32con.WM_SYSCOMMAND,
            win32con.SC_MONITORPOWER,
            -1,
        )
    except Exception:
        pass


def _force_display_driver_reset(profile: dict) -> None:
    device = str(profile.get("device", ""))
    if not device:
        return
    try:
        devmode = win32api.EnumDisplaySettings(
            device,
            win32con.ENUM_CURRENT_SETTINGS,
        )
        win32api.ChangeDisplaySettingsEx(
            device,
            devmode,
            _CDS_RESET,
        )
        win32api.ChangeDisplaySettingsEx(None, None, 0)
    except Exception:
        pass
    _wake_windows_displays()


def _pulse_monitor_signal(profile: dict) -> None:
    """Briefly remove and restore a display mode to force HDMI/DP retraining."""
    device = str(profile.get("device", ""))
    if not device:
        return
    try:
        current = win32api.EnumDisplaySettings(
            device,
            win32con.ENUM_CURRENT_SETTINGS,
        )
        current.Position_x = 0
        current.Position_y = 0
        current.PelsWidth = 0
        current.PelsHeight = 0
        current.Fields = _DM_POSITION | _DM_PELSWIDTH | _DM_PELSHEIGHT
        win32api.ChangeDisplaySettingsEx(
            device,
            current,
            _CDS_UPDATEREGISTRY,
        )
        time.sleep(0.45)
    except Exception:
        pass
    _restore_monitor_profile(profile)
    _wake_windows_displays()


def _disable_monitor_windows(device: str, profile: dict) -> tuple[bool, str]:
    try:
        devmode = win32api.EnumDisplaySettings(device, win32con.ENUM_CURRENT_SETTINGS)
        devmode.Position_x = 0
        devmode.Position_y = 0
        devmode.PelsWidth = 0
        devmode.PelsHeight = 0
        devmode.Fields = _DM_POSITION | _DM_PELSWIDTH | _DM_PELSHEIGHT

        result = win32api.ChangeDisplaySettingsEx(
            device,
            devmode,
            _CDS_UPDATEREGISTRY | _CDS_RESET,
        )
        if result != win32con.DISP_CHANGE_SUCCESSFUL:
            return False, f"Windows rechazó desactivar la salida (código {result})."

        win32api.ChangeDisplaySettingsEx(None, None, 0)
        time.sleep(0.9)
        if any(m.device == device for m in enum_monitors()):
            _restore_monitor_profile(profile)
            return False, "Windows mantuvo la salida activa."
        return True, "Salida desactivada desde Windows."
    except Exception as exc:
        _restore_monitor_profile(profile)
        return False, f"Windows no pudo desactivar la salida: {exc}"


def _disable_monitor_ddc(device: str, monitor: MonitorInfo) -> tuple[bool, str, str]:
    # Standby first; it is the most wake-friendly MCCS power state.
    for value, mode, label in (
        (0x02, "ddc_standby", "standby"),
        (0x03, "ddc_suspend", "suspensión"),
        (0x04, "ddc_off", "apagado"),
    ):
        if not set_monitor_power_value(monitor.handle, value):
            continue
        if _verify_ddc_sleep(device):
            return True, f"Monitor en {label} por DDC/CI.", mode

        # Some monitors ACK VCP D6 but ignore it. Return to ON before trying
        # another method so an acknowledged no-op never counts as success.
        fresh = next((m for m in enum_monitors() if m.device == device), monitor)
        set_monitor_power_value(fresh.handle, 0x01)
        time.sleep(0.2)

    return False, "El monitor aceptó el comando DDC/CI pero no cambió de estado.", ""


def disable_monitor(
    device: str,
    *,
    allow_last: bool = False,
    preferred_method: str = "auto",
) -> tuple[bool, str, dict | None]:
    active = enum_monitors()
    monitor = next((m for m in active if m.device == device), None)
    if monitor is None:
        return False, "La pantalla seleccionada ya no está activa.", None
    if len(active) <= 1 and not allow_last:
        return False, "No se puede apagar la última pantalla activa.", None

    try:
        profile = capture_monitor_profile(device)
        method = preferred_method if preferred_method in {"windows", "ddc"} else "ddc"
        methods = [method, "windows" if method == "ddc" else "ddc"]
        errors: list[str] = []
        failed_methods: list[str] = []

        for candidate in methods:
            if candidate == "ddc":
                ok, detail, mode = _disable_monitor_ddc(device, monitor)
                if ok:
                    profile["mode"] = mode
                    profile["power_method"] = "ddc"
                    profile["failed_methods"] = failed_methods
                    return True, f"{profile['name']} fue apagado. {detail}", profile
                failed_methods.append("ddc")
                errors.append(f"DDC/CI: {detail}")
                continue

            ok, detail = _disable_monitor_windows(device, profile)
            if ok:
                profile["mode"] = "windows_disabled"
                profile["power_method"] = "windows"
                profile["failed_methods"] = failed_methods
                return True, f"{profile['name']} fue apagado. {detail}", profile
            failed_methods.append("windows")
            errors.append(f"Windows: {detail}")

        return (
            False,
            "No se pudo apagar este monitor. " + " | ".join(errors),
            None,
        )
    except Exception as exc:
        return False, f"No se pudo apagar la pantalla: {exc}", None


def _restore_saved_brightness(profile: dict, monitor: MonitorInfo) -> bool:
    saved = profile.get("brightness")
    if saved is None:
        return get_monitor_brightness(monitor.handle) is not None
    try:
        value = max(0, min(100, int(saved)))
    except Exception:
        return False

    # DDC can need a few seconds after link renegotiation.
    for _ in range(6):
        current = get_monitor_brightness(monitor.handle)
        if current is not None:
            if set_monitor_brightness(monitor.handle, value):
                return True
            return True
        time.sleep(0.45)
        fresh = next((m for m in enum_monitors() if m.device == monitor.device), None)
        if fresh is not None:
            monitor = fresh
    return False


def enable_monitor(profile: dict) -> tuple[bool, str]:
    device = str(profile.get("device", ""))
    if not device:
        return False, "No hay información suficiente para restaurar la pantalla."

    mode = str(profile.get("mode", "windows_disabled"))
    name = str(profile.get("name") or device)

    try:
        # Always pulse the saved Windows mode first. This forces a fresh video
        # signal negotiation even if Windows still thinks the display is present.
        _restore_monitor_profile(profile)
        _wake_windows_displays()

        if mode in {"ddc_standby", "ddc_suspend", "ddc_off"}:
            # Reacquire a fresh HMONITOR/physical handle on every attempt. Handles
            # obtained before sleep are often stale after the panel wakes.
            power_ok = False
            responsive = False
            for attempt in range(8):
                _wake_windows_displays()
                monitor = next((m for m in enum_monitors() if m.device == device), None)
                if monitor is not None:
                    if set_monitor_power_value(monitor.handle, 0x01):
                        power_ok = True
                    # A successful brightness read proves DDC is alive again.
                    value = get_monitor_brightness(monitor.handle)
                    if value is not None:
                        responsive = True
                        _restore_saved_brightness(profile, monitor)
                        break
                # Deep-off monitors often need longer than standby monitors.
                time.sleep(0.55 if attempt < 3 else 0.9)

            if power_ok or responsive:
                monitor = next((m for m in enum_monitors() if m.device == device), None)
                if monitor is not None and monitor_ddc_is_awake(monitor.handle):
                    return True, f"{name} fue encendido nuevamente."

            # Some panels stop listening to DDC after standby/deep-off.
            # Force a display-driver reset before the heavier link retrain.
            _force_display_driver_reset(profile)
            for _ in range(3):
                time.sleep(0.7)
                monitor = next((m for m in enum_monitors() if m.device == device), None)
                if monitor is not None:
                    if set_monitor_power_value(monitor.handle, 0x01):
                        _restore_saved_brightness(profile, monitor)
                        return True, f"{name} fue encendido nuevamente."
                _wake_windows_displays()

            # Deep-off from older builds may require a full link retrain.
            _pulse_monitor_signal(profile)
            for _ in range(5):
                time.sleep(0.75)
                monitor = next((m for m in enum_monitors() if m.device == device), None)
                if monitor is not None:
                    if set_monitor_power_value(monitor.handle, 0x01):
                        _restore_saved_brightness(profile, monitor)
                        return True, f"{name} fue encendido nuevamente."
                    if get_monitor_brightness(monitor.handle) is not None:
                        _restore_saved_brightness(profile, monitor)
                        return True, f"{name} volvió a responder y quedó encendido."
                _wake_windows_displays()

            return (
                False,
                f"{name} no respondió al despertar. Pantallas reintentó señal de "
                "Windows y DDC/CI, pero el monitor continúa en reposo profundo.",
            )

        ok, message = _restore_monitor_profile(profile)
        if not ok:
            return False, message

        monitor = None
        for _ in range(7):
            _wake_windows_displays()
            monitor = next((m for m in enum_monitors() if m.device == device), None)
            if monitor is not None:
                set_monitor_power_value(monitor.handle, 0x01)
                _restore_saved_brightness(profile, monitor)
                return True, f"{name} fue habilitado nuevamente."
            time.sleep(0.6)

        return False, f"Windows no volvió a activar {name}."
    except Exception as exc:
        return False, f"No se pudo encender la pantalla: {exc}"



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


def get_monitor_power_value(hmonitor: int) -> int | None:
    """Read MCCS VCP D6 power mode when the monitor exposes it."""
    array, count = _physical_monitors(hmonitor)
    if not array or count <= 0:
        return None
    try:
        for physical in array:
            code_type = ctypes.c_int(0)
            current = wintypes.DWORD(0)
            maximum = wintypes.DWORD(0)
            if _dxva2.GetVCPFeatureAndVCPFeatureReply(
                physical.hPhysicalMonitor,
                0xD6,
                ctypes.byref(code_type),
                ctypes.byref(current),
                ctypes.byref(maximum),
            ):
                return int(current.value)
        return None
    finally:
        _dxva2.DestroyPhysicalMonitors(count, array)


def monitor_ddc_is_awake(hmonitor: int) -> bool:
    power = get_monitor_power_value(hmonitor)
    if power is not None:
        return power == 0x01
    return get_monitor_brightness(hmonitor) is not None


def _verify_ddc_sleep(device: str, *, timeout: float = 1.8) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        monitor = next((m for m in enum_monitors() if m.device == device), None)
        if monitor is None:
            return True
        power = get_monitor_power_value(monitor.handle)
        if power in {0x02, 0x03, 0x04, 0x05}:
            return True
        # If DDC itself goes away after the command, the panel entered sleep.
        if power is None and get_monitor_brightness(monitor.handle) is None:
            return True
        time.sleep(0.25)
    return False


def set_monitor_power_value(hmonitor: int, value: int) -> bool:
    """Write MCCS VCP D6 power mode to one logical monitor."""
    array, count = _physical_monitors(hmonitor)
    if not array or count <= 0:
        return False
    any_success = False
    try:
        for physical in array:
            if _dxva2.SetVCPFeature(
                physical.hPhysicalMonitor,
                0xD6,
                int(value) & 0xFF,
            ):
                any_success = True
        return any_success
    finally:
        _dxva2.DestroyPhysicalMonitors(count, array)


def set_monitor_power(hmonitor: int, on: bool) -> bool:
    # Use standby for off: unlike deep DPMS-off, it normally preserves DDC.
    return set_monitor_power_value(hmonitor, 0x01 if on else 0x02)


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
