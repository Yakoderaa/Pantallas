from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .build_info import BUILD_ID


RELEASE_API = "https://api.github.com/repos/Yakoderaa/Pantallas/releases/latest"
INSTALLER_ASSET = "PantallasSetup.exe"
CHECKSUM_ASSET = "PantallasSetup.exe.sha256"
USER_AGENT = "Pantallas-Updater/2.0"
MAX_INSTALLER_BYTES = 250 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
ALLOWED_INITIAL_HOSTS = {"github.com", "api.github.com"}
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


def _validate_https_url(url: str, *, download: bool = False) -> None:
    parsed = urlparse(url)
    allowed = ALLOWED_DOWNLOAD_HOSTS if download else ALLOWED_INITIAL_HOSTS
    if parsed.scheme.lower() != "https":
        raise RuntimeError("La actualización intentó usar una URL no segura.")
    if (parsed.hostname or "").lower() not in allowed:
        raise RuntimeError("La actualización intentó descargar desde un host no permitido.")


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )


def _read_url(
    url: str,
    timeout: int = 20,
    *,
    max_bytes: int = 2 * 1024 * 1024,
) -> bytes:
    _validate_https_url(url, download=url != RELEASE_API)
    with urllib.request.urlopen(_request(url), timeout=timeout) as response:
        _validate_https_url(response.geturl(), download=url != RELEASE_API)
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError("La respuesta de actualización excede el tamaño permitido.")
        return data


def _release_build_id(tag_name: str) -> int:
    match = re.fullmatch(r"build-(\d+)", tag_name.strip())
    if not match:
        raise ValueError(f"Etiqueta de actualización no reconocida: {tag_name}")
    return int(match.group(1))


class UpdateWorker(QThread):
    status = Signal(str)
    progress = Signal(int)
    no_update = Signal(int)
    installer_ready = Signal(str, int)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.status.emit("Buscando actualizaciones…")
            release = json.loads(_read_url(RELEASE_API).decode("utf-8"))
            latest_build = _release_build_id(str(release.get("tag_name", "")))

            if latest_build <= int(BUILD_ID):
                self.no_update.emit(latest_build)
                return

            assets = {
                str(asset.get("name")): str(asset.get("browser_download_url"))
                for asset in release.get("assets", [])
                if isinstance(asset, dict)
            }
            installer_url = assets.get(INSTALLER_ASSET)
            checksum_url = assets.get(CHECKSUM_ASSET)
            if not installer_url or not checksum_url:
                raise RuntimeError("La publicación no contiene el instalador o su checksum.")

            self.status.emit(f"Descargando actualización build {latest_build}…")
            expected_text = _read_url(
                checksum_url,
                max_bytes=MAX_CHECKSUM_BYTES,
            ).decode("ascii", errors="replace").strip()
            expected_hash = expected_text.split()[0].lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                raise RuntimeError("El checksum publicado no es válido.")

            update_dir = Path(tempfile.gettempdir()) / "PantallasUpdate"
            update_dir.mkdir(parents=True, exist_ok=True)
            installer_path = update_dir / f"PantallasSetup-build-{latest_build}.exe"
            partial_path = installer_path.with_suffix(".download")

            _validate_https_url(installer_url, download=True)
            request = _request(installer_url)
            with urllib.request.urlopen(request, timeout=30) as response:
                _validate_https_url(response.geturl(), download=True)
                total = int(response.headers.get("Content-Length") or 0)
                if total > MAX_INSTALLER_BYTES:
                    raise RuntimeError("El instalador publicado excede el tamaño permitido.")

                downloaded = 0
                hasher = hashlib.sha256()
                first_chunk = True
                with partial_path.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        if first_chunk:
                            first_chunk = False
                            if not chunk.startswith(b"MZ"):
                                raise RuntimeError(
                                    "El archivo descargado no tiene formato ejecutable de Windows."
                                )
                        downloaded += len(chunk)
                        if downloaded > MAX_INSTALLER_BYTES:
                            raise RuntimeError(
                                "La descarga excedió el límite de seguridad."
                            )
                        output.write(chunk)
                        hasher.update(chunk)
                        if total > 0:
                            self.progress.emit(min(100, round(downloaded * 100 / total)))

            actual_hash = hasher.hexdigest().lower()
            if actual_hash != expected_hash:
                partial_path.unlink(missing_ok=True)
                raise RuntimeError(
                    "La verificación SHA-256 falló. La actualización no se ejecutará."
                )

            partial_path.replace(installer_path)
            self.progress.emit(100)
            self.status.emit("Actualización descargada y verificada.")
            self.installer_ready.emit(str(installer_path), latest_build)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self.failed.emit("Todavía no hay una versión publicada para actualizar.")
            else:
                self.failed.emit(f"GitHub respondió con error HTTP {exc.code}.")
        except urllib.error.URLError as exc:
            self.failed.emit(f"No se pudo conectar con GitHub: {exc.reason}")
        except Exception as exc:
            self.failed.emit(str(exc))


def launch_installer_after_exit(installer_path: str) -> bool:
    installer = Path(installer_path)
    if not installer.exists():
        return False

    update_dir = installer.parent
    script = update_dir / "install_update.cmd"
    installer_quoted = str(installer).replace('"', '""')
    script.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'start "" /wait "{installer_quoted}" '
        "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS\r\n"
        'del "%~f0"\r\n',
        encoding="utf-8",
    )

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(script)],
            creationflags=flags,
            close_fds=True,
        )
        return True
    except OSError:
        return False
