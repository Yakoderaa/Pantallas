# Changelog

## 0.8.2

- Fixes the startup crash caused by residual `reconcile_active_devices` references.
- Corrects the argument type passed to `reconcile_monitors` in monitor views.
- CI now instantiates the real MainWindow and refreshes the UI in offscreen mode, so runtime initialization errors fail the build instead of reaching users.

## 0.8.1

- Clears stale DDC off-state automatically when a monitor is physically awake again.
- Adds **Ya está encendido** as a manual state-recovery action for monitors that firmware probing cannot classify reliably.
- Window rules and tray actions now use the same reconciled real monitor state.

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
