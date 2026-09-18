# Pantallas brand assets

Pantallas uses one visual family across Windows.

- `pantallas.svg` — primary application identity for the executable, installer,
  Start menu, taskbar and shortcuts.
- `pantallas-tray.svg` — simplified system-tray identity for legibility at
  very small sizes.
- `tools/generate_icons.py` — reproducibly generates Windows ICO/PNG assets
  during CI.

Generated binary assets are intentionally not committed. The release pipeline
recreates them from version-controlled drawing logic.
