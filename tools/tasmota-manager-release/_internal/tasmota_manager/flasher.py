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
    # For ESP32 family: initial flash needs the .factory.bin (bootloader +
    # partition table + app at 0x0). Regular .bin is app-only and would be
    # placed at 0x10000 for OTA updates. We always use the factory variant
    # for physical flashing to avoid the "invalid header" boot-loop.
    factory_filename: str = ""   # empty → same as filename (ESP8266 / OTA)
    flash_offset: str = "0x0"    # address passed to esptool write_flash


FIRMWARE_VARIANTS: list[FirmwareVariant] = [
    # ESP8266 – single .bin, always flashed at 0x0
    FirmwareVariant("tasmota.bin",         "ESP8266",  "Standard (ESP8266)"),
    FirmwareVariant("tasmota-lite.bin",    "ESP8266",  "Lite – kisebb méret (ESP8266)"),
    FirmwareVariant("tasmota-sensors.bin", "ESP8266",  "Sensors build (ESP8266)"),
    # ESP32 family – initial flash uses .factory.bin (bootloader+pt+app at 0x0)
    # Regular .bin is only for OTA; physical esptool flash always needs factory.
    FirmwareVariant(
        "tasmota32.bin",      "ESP32",
        "Standard (ESP32 / WROOM-32 / UE)",
        factory_filename="tasmota32.factory.bin",
        flash_offset="0x0",
    ),
    FirmwareVariant(
        "tasmota32s3.bin",    "ESP32-S3",
        "Standard (ESP32-S3)",
        factory_filename="tasmota32s3.factory.bin",
        flash_offset="0x0",
    ),
    FirmwareVariant(
        "tasmota32c3.bin",    "ESP32-C3",
        "Standard (ESP32-C3)",
        factory_filename="tasmota32c3.factory.bin",
        flash_offset="0x0",
    ),
    FirmwareVariant(
        "tasmota32c6.bin",    "ESP32-C6",
        "Standard (ESP32-C6 / WiFi-6)",
        factory_filename="tasmota32c6.factory.bin",
        flash_offset="0x0",
    ),
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
    flash_offset: str = "0x0",
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Flash firmware using esptool.

    For ESP32 family the caller must supply the .factory.bin and flash_offset="0x0"
    (bootloader + partition table + app in one image).  The regular .bin file is
    app-only and belongs at 0x10000 – using it at 0x0 causes the infamous
    "invalid header" boot-loop after erase.

    Runs esptool programmatically by temporarily redirecting stdout/stderr
    so log output can be captured and forwarded to *log_cb*.
    """
    try:
        import esptool
    except ImportError:
        raise RuntimeError("Az esptool nincs telepítve. Futtasd: pip install esptool")

    if log_cb:
        log_cb(f"Eszköz azonosítása: {port}…")
        if "factory" in firmware_path.name:
            log_cb("ℹ  Factory binary: tartalmazza a bootloadert, partíciótáblát és az alkalmazást.")
        elif chip.lower().startswith("esp32"):
            log_cb("⚠  FIGYELEM: Nem factory binary! ESP32-re első flashelésnél tasmota32.factory.bin kell.")

    # Capture esptool output
    captured = io.StringIO()
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = captured

    try:
        chip_lower = chip.lower().replace("-", "")
        is_esp32_family = chip_lower.startswith("esp32") or chip_lower == "auto"
        baud = "460800" if is_esp32_family else "115200"

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
            log_cb(f"Firmware írása ({flash_offset}): {firmware_path.name}…")

        write_args = ["--port", port, "--baud", baud, "write_flash"]

        if chip_lower == "esp8266":
            # ESP8266: force 1 MB flash size and DOUT mode for broad compatibility
            write_args += ["-fs", "1MB", "-fm", "dout"]

        write_args += [flash_offset, str(firmware_path)]
        esptool.main(write_args)

    finally:
        sys.stdout, sys.stderr = orig_stdout, orig_stderr
        for line in captured.getvalue().splitlines():
            if line.strip() and log_cb:
                log_cb(f"[esptool] {line}")

    if log_cb:
        log_cb("✅ Égetés befejezve! Az eszköz újraindul.")
