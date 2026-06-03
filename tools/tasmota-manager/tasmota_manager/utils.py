"""Serial port detection and shared utility helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import serial.tools.list_ports

# Known USB-Serial adapter VID/PID pairs
_KNOWN_DRIVERS: list[tuple[tuple[int, int], str]] = [
    ((0x1A86, 0x7523), "CH340"),
    ((0x1A86, 0x5523), "CH340"),
    ((0x1A86, 0x55D4), "CH343"),
    ((0x10C4, 0xEA60), "CP2102"),
    ((0x10C4, 0xEA70), "CP2105"),
    ((0x0403, 0x6001), "FTDI"),
    ((0x0403, 0x6010), "FTDI"),
    ((0x0403, 0x6014), "FTDI"),
    ((0x0403, 0x6015), "FTDI"),
    ((0x303A, 0x1001), "ESP32-S3 USB"),  # built-in USB CDC
    ((0x239A, 0x80B0), "WEMOS"),
]


@dataclass
class SerialPortInfo:
    device: str
    description: str
    driver: str
    vid: Optional[int]
    pid: Optional[int]

    def display_label(self) -> str:
        if self.driver and self.driver != "Unknown":
            return f"{self.device}  ({self.driver})"
        return f"{self.device}  ({self.description[:30]})"


def detect_driver(vid: Optional[int], pid: Optional[int]) -> str:
    if vid is None or pid is None:
        return "Unknown"
    for (v, p), name in _KNOWN_DRIVERS:
        if vid == v and pid == p:
            return name
    return "Unknown"


def list_serial_ports(esp_only: bool = False) -> list[SerialPortInfo]:
    """Return available serial ports.

    If *esp_only* is True, only well-known ESP programmer adapters are returned.
    """
    ports = serial.tools.list_ports.comports()
    result: list[SerialPortInfo] = []
    for p in ports:
        driver = detect_driver(p.vid, p.pid)
        if esp_only and driver == "Unknown":
            continue
        result.append(
            SerialPortInfo(
                device=p.device,
                description=p.description or "",
                driver=driver,
                vid=p.vid,
                pid=p.pid,
            )
        )
    return sorted(result, key=lambda x: x.device)


def rssi_to_bars(rssi: Optional[int]) -> str:
    """Convert RSSI dBm value to a 5-bar visual indicator."""
    if rssi is None:
        return "─────"
    if rssi >= -55:
        return "▮▮▮▮▮"
    if rssi >= -65:
        return "▮▮▮▮▯"
    if rssi >= -75:
        return "▮▮▮▯▯"
    if rssi >= -85:
        return "▮▮▯▯▯"
    return "▮▯▯▯▯"


def rssi_label(rssi: Optional[int]) -> str:
    if rssi is None:
        return "N/A"
    if rssi >= -55:
        return "Kiváló"
    if rssi >= -65:
        return "Jó"
    if rssi >= -75:
        return "Elfogadható"
    if rssi >= -85:
        return "Gyenge"
    return "Nagyon gyenge"
