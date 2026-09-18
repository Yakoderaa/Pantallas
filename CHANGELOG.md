# Changelog

## 0.8.0

- Adaptive per-monitor power strategy with Automatic, Windows and DDC/CI modes.
- DDC power commands are verified instead of trusting a successful API return.
- Failed DDC wake attempts make Automatic mode prefer Windows next time.
- Removed the monitor-distribution graphic and all editable distribution UI.
- Added a unified Pantallas visual identity for application, installer, taskbar,
  Start menu and system tray.
- Added reproducible icon generation.
- Hardened GitHub Actions permissions and split build/release permissions.
- Added CodeQL, Dependabot, CODEOWNERS, security policy and proprietary license.
- Reorganized project documentation.

## 0.7.0

- Fixed persistent DDC standby/off state.
- Added global position-lock toggle in the tray.
- Removed editable monitor-layout controls.

## 0.6.0

- Added monitor ordering, last-monitor safety and brightness recovery.

## 0.5.0

- Integrated monitor controls and custom monitor names.

## 0.4.0

- Migrated Windows packaging from PyInstaller onefile to onedir.

## 0.3.0

- Added system tray, startup with Windows and monitor power controls.
