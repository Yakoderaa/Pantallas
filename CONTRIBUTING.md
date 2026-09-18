# Contributing to Pantallas

Pantallas is a proprietary source-available project. Contributions are welcome
only under terms accepted by the repository owner; submitting a patch does not
change the license of the project.

## Development setup

1. Use Windows 10 or Windows 11.
2. Install Python 3.11.
3. Create a virtual environment.
4. Install `requirements.txt`.
5. Run `python app.py`.

For release tooling, also install the packages used by
`tools/generate_icons.py` and PyInstaller.

## Pull requests

Keep changes focused. For monitor power changes, document:

- connection type (HDMI/DisplayPort/dock);
- whether brightness DDC/CI works;
- the power method tested;
- behavior when waking the monitor.

Do not commit generated installers, build directories, virtual environments,
credentials, API tokens, certificates, or signing keys.

## Style

- Python 3.11+.
- Type annotations where practical.
- User-visible errors should explain what failed without exposing secrets.
- Windows-specific behavior should fail safely and preserve at least one
  usable display unless the user explicitly disabled that protection.
