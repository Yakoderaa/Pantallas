# Architecture

Pantallas is a native Windows desktop application built with Python and
PySide6.

## Main components

| Component | Responsibility |
|---|---|
| `app.py` | Process identity, QApplication lifecycle and startup mode |
| `pantallas/main_window.py` | Main navigation, tray menu, monitor actions and updater orchestration |
| `pantallas/windows_api.py` | Win32 monitor enumeration, DDC/CI, window enumeration and movement |
| `pantallas/rules.py` | Persistent application-position rules and enforcement |
| `pantallas/power_profiles.py` | Per-monitor adaptive power-method learning |
| `pantallas/monitor_state.py` | Persisted off-monitor state |
| `pantallas/preferences.py` | Per-user application preferences and Windows startup |
| `pantallas/update_service.py` | GitHub release discovery, download, SHA-256 validation and installer handoff |
| `assets/brand` | Source visual identity |
| `tools/generate_icons.py` | Reproducible Windows ICO generation |
| `installer/Pantallas.iss` | Inno Setup installer |

## Release path

`main` → smoke test → PyInstaller onedir → runtime verification → Inno Setup
→ SHA-256 → CI artifact → release job.

The build job is read-only. Only the dedicated release job receives
`contents: write`.
