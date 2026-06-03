"""Board pinout definitions for visual board monitor."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PinDef:
    label: str              # Display label, e.g. "D1", "GPIO5"
    gpio: Optional[int]     # GPIO number (None for power/GND/UART)
    side: str               # "left" or "right"
    row: int                # Row position (0-based)
    boot_sensitive: bool = False
    adc_only: bool = False
    is_power: bool = False  # VCC, GND, 3V3, 5V
    is_uart: bool = False


@dataclass
class BoardLayout:
    name: str
    chip: str               # "ESP8266" | "ESP32" | "ESP32-S3" | "ESP32-C3"
    display_width: int      # chars for the board box
    pins: list[PinDef] = field(default_factory=list)
    # D-pin alias mapping: {gpio_number: "D1", ...}
    gpio_to_dpin: dict[int, str] = field(default_factory=dict)

    def pin_by_gpio(self, gpio: int) -> Optional[PinDef]:
        for p in self.pins:
            if p.gpio == gpio:
                return p
        return None


# ---------------------------------------------------------------------------
# Wemos D1 Mini (ESP8266)
# ---------------------------------------------------------------------------

D1_MINI = BoardLayout(
    name="Wemos D1 Mini",
    chip="ESP8266",
    display_width=52,
    gpio_to_dpin={
        16: "D0",
        5:  "D1",
        4:  "D2",
        0:  "D3",
        2:  "D4",
        14: "D5",
        12: "D6",
        13: "D7",
        15: "D8",
    },
    pins=[
        # Left side (top → bottom)
        PinDef("RST",  None,  "left",  0, is_power=True),
        PinDef("A0",   None,  "left",  1, adc_only=True),
        PinDef("D0",   16,    "left",  2),
        PinDef("D5",   14,    "left",  3),
        PinDef("D6",   12,    "left",  4),
        PinDef("D7",   13,    "left",  5),
        PinDef("D8",   15,    "left",  6, boot_sensitive=True),
        PinDef("3V3",  None,  "left",  7, is_power=True),
        # Right side (top → bottom)
        PinDef("TX",   None,  "right", 0, is_uart=True),
        PinDef("RX",   None,  "right", 1, is_uart=True),
        PinDef("D1",   5,     "right", 2),
        PinDef("D2",   4,     "right", 3),
        PinDef("D3",   0,     "right", 4, boot_sensitive=True),
        PinDef("D4",   2,     "right", 5, boot_sensitive=True),
        PinDef("GND",  None,  "right", 6, is_power=True),
        PinDef("5V",   None,  "right", 7, is_power=True),
    ],
)

# ---------------------------------------------------------------------------
# NodeMCU v3 (ESP8266)
# ---------------------------------------------------------------------------

NODEMCU = BoardLayout(
    name="NodeMCU v3 (ESP8266)",
    chip="ESP8266",
    display_width=52,
    gpio_to_dpin={
        16: "D0", 5: "D1", 4: "D2", 0: "D3",
        2: "D4", 14: "D5", 12: "D6", 13: "D7", 15: "D8", 3: "D9", 1: "D10",
    },
    pins=[
        PinDef("A0",   None,  "left",  0, adc_only=True),
        PinDef("RSV",  None,  "left",  1, is_power=True),
        PinDef("RSV",  None,  "left",  2, is_power=True),
        PinDef("SD3",  10,    "left",  3),
        PinDef("SD2",  9,     "left",  4),
        PinDef("SD1",  None,  "left",  5),
        PinDef("CMD",  None,  "left",  6),
        PinDef("SD0",  None,  "left",  7),
        PinDef("CLK",  None,  "left",  8),
        PinDef("GND",  None,  "left",  9, is_power=True),
        PinDef("3V3",  None,  "left",  10, is_power=True),
        PinDef("EN",   None,  "left",  11),
        PinDef("RST",  None,  "left",  12),
        PinDef("GND",  None,  "left",  13, is_power=True),
        PinDef("Vin",  None,  "left",  14, is_power=True),
        PinDef("D0",   16,    "right", 0),
        PinDef("D1",   5,     "right", 1),
        PinDef("D2",   4,     "right", 2),
        PinDef("D3",   0,     "right", 3, boot_sensitive=True),
        PinDef("D4",   2,     "right", 4, boot_sensitive=True),
        PinDef("3V3",  None,  "right", 5, is_power=True),
        PinDef("GND",  None,  "right", 6, is_power=True),
        PinDef("D5",   14,    "right", 7),
        PinDef("D6",   12,    "right", 8),
        PinDef("D7",   13,    "right", 9),
        PinDef("D8",   15,    "right", 10, boot_sensitive=True),
        PinDef("RX",   None,  "right", 11, is_uart=True),
        PinDef("TX",   None,  "right", 12, is_uart=True),
        PinDef("GND",  None,  "right", 13, is_power=True),
        PinDef("3V3",  None,  "right", 14, is_power=True),
    ],
)

# ---------------------------------------------------------------------------
# ESP32 DevKit v1 (38-pin)
# ---------------------------------------------------------------------------

ESP32_DEVKIT = BoardLayout(
    name="ESP32 DevKit V1",
    chip="ESP32",
    display_width=58,
    gpio_to_dpin={},   # ESP32 uses GPIO numbers directly
    pins=[
        # Left side (top → bottom)
        PinDef("3V3",  None, "left",  0, is_power=True),
        PinDef("EN",   None, "left",  1),
        PinDef("VP",   36,   "left",  2, adc_only=True),
        PinDef("VN",   39,   "left",  3, adc_only=True),
        PinDef("34",   34,   "left",  4, adc_only=True),
        PinDef("35",   35,   "left",  5, adc_only=True),
        PinDef("32",   32,   "left",  6),
        PinDef("33",   33,   "left",  7),
        PinDef("25",   25,   "left",  8),
        PinDef("26",   26,   "left",  9),
        PinDef("27",   27,   "left",  10),
        PinDef("14",   14,   "left",  11),
        PinDef("12",   12,   "left",  12),
        PinDef("GND",  None, "left",  13, is_power=True),
        PinDef("13",   13,   "left",  14),
        PinDef("D2",   9,    "left",  15),
        PinDef("D3",   10,   "left",  16),
        PinDef("CMD",  11,   "left",  17),
        PinDef("5V",   None, "left",  18, is_power=True),
        # Right side (top → bottom)
        PinDef("GND",  None, "right", 0, is_power=True),
        PinDef("23",   23,   "right", 1),
        PinDef("22",   22,   "right", 2),
        PinDef("TX",   1,    "right", 3, is_uart=True),
        PinDef("RX",   3,    "right", 4, is_uart=True),
        PinDef("21",   21,   "right", 5),
        PinDef("GND",  None, "right", 6, is_power=True),
        PinDef("19",   19,   "right", 7),
        PinDef("18",   18,   "right", 8),
        PinDef("5",    5,    "right", 9),
        PinDef("17",   17,   "right", 10),
        PinDef("16",   16,   "right", 11),
        PinDef("4",    4,    "right", 12),
        PinDef("0",    0,    "right", 13, boot_sensitive=True),
        PinDef("2",    2,    "right", 14),
        PinDef("15",   15,   "right", 15),
        PinDef("D1",   8,    "right", 16),
        PinDef("D0",   7,    "right", 17),
        PinDef("CLK",  6,    "right", 18),
    ],
)

# ---------------------------------------------------------------------------
# ESP32-S3 DevKit
# ---------------------------------------------------------------------------

ESP32_S3 = BoardLayout(
    name="ESP32-S3 DevKit",
    chip="ESP32-S3",
    display_width=58,
    gpio_to_dpin={},
    pins=[
        PinDef("3V3",  None, "left",  0, is_power=True),
        PinDef("3V3",  None, "left",  1, is_power=True),
        PinDef("RST",  None, "left",  2),
        PinDef("4",    4,    "left",  3),
        PinDef("5",    5,    "left",  4),
        PinDef("6",    6,    "left",  5),
        PinDef("7",    7,    "left",  6),
        PinDef("15",   15,   "left",  7),
        PinDef("16",   16,   "left",  8),
        PinDef("17",   17,   "left",  9),
        PinDef("18",   18,   "left",  10),
        PinDef("8",    8,    "left",  11),
        PinDef("3",    3,    "left",  12),
        PinDef("46",   46,   "left",  13),
        PinDef("9",    9,    "left",  14),
        PinDef("10",   10,   "left",  15),
        PinDef("11",   11,   "left",  16),
        PinDef("12",   12,   "left",  17),
        PinDef("13",   13,   "left",  18),
        PinDef("14",   14,   "left",  19),
        PinDef("5V",   None, "right", 0, is_power=True),
        PinDef("GND",  None, "right", 1, is_power=True),
        PinDef("TX",   43,   "right", 2, is_uart=True),
        PinDef("RX",   44,   "right", 3, is_uart=True),
        PinDef("1",    1,    "right", 4),
        PinDef("2",    2,    "right", 5),
        PinDef("42",   42,   "right", 6),
        PinDef("41",   41,   "right", 7),
        PinDef("40",   40,   "right", 8),
        PinDef("39",   39,   "right", 9),
        PinDef("38",   38,   "right", 10),
        PinDef("37",   37,   "right", 11),
        PinDef("36",   36,   "right", 12),
        PinDef("35",   35,   "right", 13),
        PinDef("0",    0,    "right", 14, boot_sensitive=True),
        PinDef("45",   45,   "right", 15),
        PinDef("48",   48,   "right", 16),
        PinDef("47",   47,   "right", 17),
        PinDef("21",   21,   "right", 18),
        PinDef("GND",  None, "right", 19, is_power=True),
    ],
)


# ---------------------------------------------------------------------------
# ESP-WROOM32-CH340  (38-pin, identical pinout to DevKit V1, CH340 USB chip)
# ---------------------------------------------------------------------------

ESP32_WROOM_CH340 = BoardLayout(
    name="ESP-WROOM32-CH340",
    chip="ESP32",
    display_width=58,
    gpio_to_dpin={},
    pins=[
        # Left side (top → bottom)
        PinDef("3V3",  None, "left",  0, is_power=True),
        PinDef("EN",   None, "left",  1),
        PinDef("VP",   36,   "left",  2, adc_only=True),
        PinDef("VN",   39,   "left",  3, adc_only=True),
        PinDef("34",   34,   "left",  4, adc_only=True),
        PinDef("35",   35,   "left",  5, adc_only=True),
        PinDef("32",   32,   "left",  6),
        PinDef("33",   33,   "left",  7),
        PinDef("25",   25,   "left",  8),
        PinDef("26",   26,   "left",  9),
        PinDef("27",   27,   "left",  10),
        PinDef("14",   14,   "left",  11),
        PinDef("12",   12,   "left",  12),
        PinDef("GND",  None, "left",  13, is_power=True),
        PinDef("13",   13,   "left",  14),
        PinDef("D2",   9,    "left",  15),
        PinDef("D3",   10,   "left",  16),
        PinDef("CMD",  11,   "left",  17),
        PinDef("5V",   None, "left",  18, is_power=True),
        # Right side (top → bottom)
        PinDef("GND",  None, "right", 0, is_power=True),
        PinDef("23",   23,   "right", 1),
        PinDef("22",   22,   "right", 2),
        PinDef("TX",   1,    "right", 3, is_uart=True),
        PinDef("RX",   3,    "right", 4, is_uart=True),
        PinDef("21",   21,   "right", 5),
        PinDef("GND",  None, "right", 6, is_power=True),
        PinDef("19",   19,   "right", 7),
        PinDef("18",   18,   "right", 8),
        PinDef("5",    5,    "right", 9),
        PinDef("17",   17,   "right", 10),
        PinDef("16",   16,   "right", 11),
        PinDef("4",    4,    "right", 12),
        PinDef("0",    0,    "right", 13, boot_sensitive=True),
        PinDef("2",    2,    "right", 14),
        PinDef("15",   15,   "right", 15),
        PinDef("D1",   8,    "right", 16),
        PinDef("D0",   7,    "right", 17),
        PinDef("CLK",  6,    "right", 18),
    ],
)

# ---------------------------------------------------------------------------
# ESP32-DEVKIT-32UE  (30-pin, U.FL external antenna – compact devkit)
# ---------------------------------------------------------------------------

ESP32_DEVKIT_32UE = BoardLayout(
    name="ESP32-DEVKIT-32UE",
    chip="ESP32",
    display_width=52,
    gpio_to_dpin={},
    pins=[
        # Left side (top → bottom)
        PinDef("3V3",  None, "left",  0, is_power=True),
        PinDef("EN",   None, "left",  1),
        PinDef("VP",   36,   "left",  2, adc_only=True),
        PinDef("VN",   39,   "left",  3, adc_only=True),
        PinDef("34",   34,   "left",  4, adc_only=True),
        PinDef("35",   35,   "left",  5, adc_only=True),
        PinDef("32",   32,   "left",  6),
        PinDef("33",   33,   "left",  7),
        PinDef("25",   25,   "left",  8),
        PinDef("26",   26,   "left",  9),
        PinDef("27",   27,   "left",  10),
        PinDef("14",   14,   "left",  11),
        PinDef("12",   12,   "left",  12),
        PinDef("GND",  None, "left",  13, is_power=True),
        PinDef("13",   13,   "left",  14),
        # Right side (top → bottom)
        PinDef("GND",  None, "right", 0, is_power=True),
        PinDef("23",   23,   "right", 1),
        PinDef("22",   22,   "right", 2),
        PinDef("TX",   1,    "right", 3, is_uart=True),
        PinDef("RX",   3,    "right", 4, is_uart=True),
        PinDef("21",   21,   "right", 5),
        PinDef("GND",  None, "right", 6, is_power=True),
        PinDef("19",   19,   "right", 7),
        PinDef("18",   18,   "right", 8),
        PinDef("5",    5,    "right", 9),
        PinDef("17",   17,   "right", 10),
        PinDef("16",   16,   "right", 11),
        PinDef("4",    4,    "right", 12),
        PinDef("0",    0,    "right", 13, boot_sensitive=True),
        PinDef("2",    2,    "right", 14),
    ],
)


ALL_BOARDS: list[BoardLayout] = [
    D1_MINI, NODEMCU, ESP32_DEVKIT, ESP32_WROOM_CH340, ESP32_DEVKIT_32UE, ESP32_S3
]
BOARD_BY_NAME: dict[str, BoardLayout] = {b.name: b for b in ALL_BOARDS}

CHIP_DEFAULT_BOARD: dict[str, str] = {
    "ESP8266":  "Wemos D1 Mini",
    "ESP32":    "ESP32 DevKit V1",
    "ESP32-S3": "ESP32-S3 DevKit",
    "ESP32-C3": "ESP32 DevKit V1",
}

# ---------------------------------------------------------------------------
# Tasmota Module ID mapping
# ---------------------------------------------------------------------------
# Maps board/device name → Tasmota "Module N" command value.
# For ESP32 boards Tasmota uses Module 0 (ESP32 Generic).
# For ESP8266 boards Module 18 = Generic.
# Sonoff-branded devices have dedicated module IDs.
BOARD_TO_TASMOTA_MODULE: dict[str, int] = {
    "Wemos D1 Mini":         18,   # Generic ESP8266
    "NodeMCU v3 (ESP8266)":  18,   # Generic ESP8266
    "ESP32 DevKit V1":        0,   # Generic ESP32
    "ESP-WROOM32-CH340":      0,   # Generic ESP32
    "ESP32-DEVKIT-32UE":      0,   # Generic ESP32
    "ESP32-S3 DevKit":        0,   # Generic ESP32-S3
    "Sonoff Basic":           1,
    "Sonoff S20":             8,
    "Sonoff TH":              4,
    "Sonoff Dual":            5,
    "Sonoff 4CH":             7,
    "Sonoff Mini":           38,
}

# Reverse: Tasmota module ID → default board name to show in Board tab.
# When multiple boards share the same module ID, pick the most common one.
TASMOTA_MODULE_TO_BOARD: dict[int, str] = {
    18: "Wemos D1 Mini",
     0: "ESP32 DevKit V1",
     1: "Sonoff Basic",
     8: "Sonoff S20",
     4: "Sonoff TH",
     5: "Sonoff Dual",
     7: "Sonoff 4CH",
    38: "Sonoff Mini",
}

# All selectable device/board names for the Config "Modul" and Board selects.
# Boards with a visual diagram come first, then Sonoff device-only entries.
MODULE_SELECT_OPTIONS: list[tuple[str, str]] = (
    [(b.name, b.name) for b in ALL_BOARDS]
    + [
        ("Sonoff Basic (M1)",    "Sonoff Basic"),
        ("Sonoff S20 (M8)",      "Sonoff S20"),
        ("Sonoff TH (M4)",       "Sonoff TH"),
        ("Sonoff Dual (M5)",     "Sonoff Dual"),
        ("Sonoff 4CH (M7)",      "Sonoff 4CH"),
        ("Sonoff Mini (M38)",    "Sonoff Mini"),
    ]
)
