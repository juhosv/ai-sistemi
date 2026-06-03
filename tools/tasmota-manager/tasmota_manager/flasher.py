"""Tasmota firmware download from GitHub and flashing via esptool."""
from __future__ import annotations

import io
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

GITHUB_API_LATEST = (
    "https://api.github.com/repos/arendst/Tasmota/releases/latest"
)

CACHE_DIR = Path(tempfile.gettempdir()) / "tasmota_manager_fw"


@dataclass
class FirmwareVariant:
    filename: str
    chip: str
    description: str


FIRMWARE_VARIANTS: list[FirmwareVariant] = [
    FirmwareVariant("tasmota.bin",        "ESP8266",  "Standard (ESP8266)"),
    FirmwareVariant("tasmota-lite.bin",   "ESP8266",  "Lite – kisebb méret (ESP8266)"),
    FirmwareVariant("tasmota-sensors.bin","ESP8266",  "Sensors build (ESP8266)"),
    FirmwareVariant("tasmota32.bin",      "ESP32",    "Standard (ESP32)"),
    FirmwareVariant("tasmota32s3.bin",    "ESP32-S3", "Standard (ESP32-S3)"),
    FirmwareVariant("tasmota32c3.bin",    "ESP32-C3", "Standard (ESP32-C3)"),
]


@dataclass
class ReleaseInfo:
    tag: str
    assets: dict[str, str]   # filename → download_url


def get_latest_release(log_cb: Optional[Callable[[str], None]] = None) -> ReleaseInfo:
    """Fetch latest Tasmota release info from GitHub API."""
    if log_cb:
        log_cb("GitHub API: legfrissebb verzió ellenőrzése…")
    resp = requests.get(GITHUB_API_LATEST, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    tag = data["tag_name"]
    assets = {a["name"]: a["browser_download_url"] for a in data["assets"]}
    if log_cb:
        log_cb(f"Legfrissebb verzió: {tag}")
    return ReleaseInfo(tag=tag, assets=assets)


def download_firmware(
    url: str,
    dest: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """Download firmware binary to *dest*, reporting byte progress."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if log_cb:
        log_cb(f"Letöltés: {dest.name}…")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=16384):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)
    if log_cb:
        size_kb = dest.stat().st_size // 1024
        log_cb(f"Letöltés kész: {dest.name} ({size_kb} kB)")
    return dest


def get_cached_firmware(filename: str) -> Optional[Path]:
    path = CACHE_DIR / filename
    return path if path.exists() else None


def flash_firmware(
    port: str,
    firmware_path: Path,
    chip: str = "auto",
    erase: bool = True,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Flash firmware using esptool.

    Runs esptool programmatically by temporarily redirecting stdout/stderr
    so log output can be captured and forwarded to *log_cb*.
    """
    try:
        import esptool
    except ImportError:
        raise RuntimeError("Az esptool nincs telepítve. Futtasd: pip install esptool")

    if log_cb:
        log_cb(f"Eszköz azonosítása: {port}…")

    # Capture esptool output
    captured = io.StringIO()
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = captured

    try:
        baud = "460800" if chip.lower() in ("esp32", "esp32s3", "esp32c3") else "115200"

        if erase:
            if log_cb:
                log_cb("Flash törlése…")
            sys.stdout = sys.stderr = captured
            esptool.main(["--port", port, "--baud", baud, "erase_flash"])
            sys.stdout, sys.stderr = orig_stdout, orig_stderr
            for line in captured.getvalue().splitlines():
                if line.strip() and log_cb:
                    log_cb(f"[esptool] {line}")
            captured.truncate(0)
            captured.seek(0)
            sys.stdout = sys.stderr = captured

        if log_cb:
            log_cb(f"Firmware írása: {firmware_path.name}…")

        write_args = ["--port", port, "--baud", baud, "write_flash"]
        if chip.lower() == "esp8266":
            write_args += ["-fs", "1MB", "-fm", "dout"]
        write_args += ["0x0", str(firmware_path)]

        esptool.main(write_args)

    finally:
        sys.stdout, sys.stderr = orig_stdout, orig_stderr
        for line in captured.getvalue().splitlines():
            if line.strip() and log_cb:
                log_cb(f"[esptool] {line}")

    if log_cb:
        log_cb("Égetés befejezve! Az eszköz újraindul.")
