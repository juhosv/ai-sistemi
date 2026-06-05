"""Board Monitor tab – real-time visual pin state map + device info panel."""
from __future__ import annotations

import asyncio
import json
import re
import time as _time_module
from datetime import datetime
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
    TabPane,
)

from textual.widgets import Input

from tasmota_manager.board_layouts import (
    ALL_BOARDS,
    BOARD_BY_NAME,
    BoardLayout,
    PinDef,
    D1_MINI,
)
from tasmota_manager.config_builder import (
    GPIO_FUNCTION_TYPES,
    GPIO_TYPE_BY_ID,
    assign_tasmota_codes,
    compute_gpio_instances,
    instance_label,
)
from tasmota_manager.utils import rssi_to_bars, rssi_label

# Commandable output type_ids and their Tasmota command prefix
_OUTPUT_CMD: dict[str, str] = {
    "relay": "POWER",
    "pwm":   "Dimmer",
    "led":   "POWER",
}

# ---------------------------------------------------------------------------
# Reverse mapping: Tasmota numeric code → type_id
# Used to decode the GPIO command response from the device.
# ---------------------------------------------------------------------------

_TASMOTA_CODE_TO_TYPE: dict[int, str] = {}
for _gt in GPIO_FUNCTION_TYPES:
    for _code in _gt.base_codes:
        _TASMOTA_CODE_TO_TYPE[_code] = _gt.type_id


# ---------------------------------------------------------------------------
# Helpers – JSON parsing (shared with config_screen but self-contained here)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[dict]:
    """Return the first JSON object found in *text*, or None."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    return None
    return None


def _parse_status1(lines: list[str]) -> dict:
    """StatusPRM / Status → hostname, topic, module."""
    result: dict = {}
    for line in lines:
        if "StatusPRM" not in line and '"Status"' not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        block = data.get("StatusPRM") or data.get("Status") or {}
        for src, dst in [("Topic", "topic"), ("DeviceName", "hostname"),
                         ("FriendlyName", "friendly"), ("Module", "module_id")]:
            if src in block:
                result[dst] = block[src]
    return result


def _parse_status2(lines: list[str]) -> dict:
    """StatusFWR → firmware version, chip/hardware string."""
    result: dict = {}
    for line in lines:
        if "StatusFWR" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        fwr = data.get("StatusFWR", {})
        version_raw = fwr.get("Version", "")
        # Strip build variant e.g. "14.3.0(tasmota32)" → "14.3.0"
        version = re.sub(r"\(.*\)", "", version_raw).strip()
        if version:
            result["firmware"] = version
        hw = fwr.get("Hardware", "")
        if hw:
            result["hardware"] = hw
    # Boot-log fallback for chip family
    for line in lines:
        if "ESP-IDF" in line:
            result.setdefault("hardware", "ESP32")
    return result


def _parse_status5(lines: list[str]) -> dict:
    """StatusNET → SSID, IP, RSSI (dBm), MAC."""
    result: dict = {}
    for line in lines:
        if "StatusNET" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        net = data.get("StatusNET", {})
        for src, dst in [("SSId", "ssid"), ("IPAddress", "ip"), ("Mac", "mac")]:
            if net.get(src):
                result[dst] = net[src]
        # Signal (dBm) takes precedence over RSSI (%)
        sig = net.get("Signal")
        rssi_pct = net.get("RSSI")
        if sig is not None:
            try:
                result["rssi"] = int(sig)
            except ValueError:
                pass
        elif rssi_pct is not None:
            try:
                pct = int(rssi_pct)
                result["rssi"] = pct if pct < 0 else pct // 2 - 100
            except ValueError:
                pass
    return result


def _parse_status10(lines: list[str]) -> dict:
    """StatusSNS → sensor readings dict + energy dict + switch states + counters."""
    result: dict = {"sensors": {}, "energy": {}, "switches": {}, "counters": {}}
    _SENSOR_KEYS = {"AM2301", "DHT11", "DHT22", "DS18B20", "BMP280",
                    "BME280", "BME680", "SHT3X", "AHT20", "SCD40",
                    "SI7021", "HTU21", "MCP9808", "TSL2561"}
    for line in lines:
        if "StatusSNS" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        sns = data.get("StatusSNS", {})
        for key, val in sns.items():
            if key in _SENSOR_KEYS and isinstance(val, dict):
                result["sensors"][key] = val
            elif key == "ENERGY" and isinstance(val, dict):
                result["energy"] = val
            else:
                # Switch1, Switch2, ... → ON/OFF physical state
                m = re.match(r"Switch(\d+)$", key)
                if m and isinstance(val, str):
                    result["switches"][int(m.group(1))] = (val == "ON")
                    continue
                # COUNTER.C1, COUNTER.C2, ... nested object format
                # e.g. {"StatusSNS": {..., "COUNTER": {"C1": 1251}}}
                if key == "COUNTER" and isinstance(val, dict):
                    for ck, cv in val.items():
                        cm = re.match(r"C(\d+)$", ck)
                        if cm:
                            try:
                                result["counters"][int(cm.group(1))] = int(cv)
                            except (TypeError, ValueError):
                                pass
    return result


def _parse_status11(lines: list[str]) -> dict:
    """StatusSTS → power states, uptime, WiFi signal, PWM channels."""
    result: dict = {"power": {}, "uptime": "", "wifi_rssi": None, "pwm": {}}
    for line in lines:
        if "StatusSTS" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        sts = data.get("StatusSTS", {})
        result["uptime"] = str(sts.get("Uptime", ""))
        # POWER1, POWER2, ...
        for key, val in sts.items():
            m = re.match(r"POWER(\d*)", key)
            if m:
                idx = int(m.group(1) or "1")
                result["power"][idx] = (val == "ON")
        # Channel array: [pct0, pct1, ...] – PWM duty cycle 0-100 per channel (1-indexed)
        channels = sts.get("Channel")
        if isinstance(channels, list):
            for i, pct in enumerate(channels):
                try:
                    result["pwm"][i + 1] = int(pct)
                except (TypeError, ValueError):
                    pass
        # Also accept individual Dimmer1, Dimmer2, ... keys
        for key, val in sts.items():
            m = re.match(r"Dimmer(\d+)$", key)
            if m:
                try:
                    result["pwm"][int(m.group(1))] = int(val)
                except (TypeError, ValueError):
                    pass
        # Inline WiFi
        wifi = sts.get("Wifi", {})
        if isinstance(wifi, dict):
            sig = wifi.get("Signal")
            rssi_pct = wifi.get("RSSI")
            if sig is not None:
                try:
                    result["wifi_rssi"] = int(sig)
                except ValueError:
                    pass
            elif rssi_pct is not None:
                try:
                    pct = int(rssi_pct)
                    result["wifi_rssi"] = pct if pct < 0 else pct // 2 - 100
                except ValueError:
                    pass
    # Also check tele STATE lines (has Uptime + Wifi)
    for line in lines:
        if '"Uptime"' not in line and '"POWER"' not in line:
            continue
        data = _extract_json(line)
        if not data or not isinstance(data, dict):
            continue
        if "Uptime" in data and not result["uptime"]:
            result["uptime"] = str(data["Uptime"])
        for key, val in data.items():
            m = re.match(r"POWER(\d*)", key)
            if m:
                idx = int(m.group(1) or "1")
                result["power"].setdefault(idx, val == "ON")
    return result


def _parse_status4(lines: list[str]) -> dict:
    """StatusMEM → free heap, program size."""
    result: dict = {}
    for line in lines:
        if "StatusMEM" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        mem = data.get("StatusMEM", {})
        if "Heap" in mem:
            result["heap"] = int(mem["Heap"])
        if "ProgramSize" in mem:
            result["program_size"] = int(mem["ProgramSize"])
        if "Free" in mem:
            result["flash_free"] = int(mem["Free"])
    return result


def _parse_status6(lines: list[str]) -> dict:
    """StatusMQT → MQTT broker host/port, connection count, client."""
    result: dict = {}
    for line in lines:
        if "StatusMQT" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        mqt = data.get("StatusMQT", {})
        for src, dst in [
            ("MqttHost",   "mqtt_host"),
            ("MqttPort",   "mqtt_port"),
            ("MqttCount",  "mqtt_count"),
            ("MqttClientMask", "mqtt_client"),
        ]:
            if src in mqt:
                result[dst] = mqt[src]
    return result


def _name_to_type(name: str) -> Optional[str]:
    """
    Map a Tasmota GPIO function name to our type_id.
    e.g. 'Relay1', 'Relay2 (22)' → 'relay'
         'Switch1 (160)'         → 'switch'
    """
    n = name.lower()
    if "relay" in n:       return "relay"
    if "switch" in n:      return "switch"
    if "button" in n:      return "button"
    if "counter" in n:     return "counter"
    if "pwm" in n:         return "pwm"
    if "ledlink" in n:     return "led"
    if "led" in n:         return "led"
    if "am2301" in n or "dht22" in n: return "dht22"
    if "dht11" in n:       return "dht11"
    if "ds18" in n:        return "ds18b20"
    if "i2c" in n and "scl" in n: return "i2c_scl"
    if "i2c" in n and "sda" in n: return "i2c_sda"
    return None


def _to_type(val: object) -> Optional[str]:
    """
    Resolve a Tasmota GPIO value (int code or name string) to our type_id.

    Tasmota returns values in multiple formats depending on version:
      - Integer:          21                    (numeric code)
      - String with code: "Relay1 (21)"         (name + code in parens)
      - String only:      "Relay1"              (name, no code)
      - "None (0)":       unassigned pin        → skip
    """
    if isinstance(val, int):
        if val == 0:
            return None
        return _TASMOTA_CODE_TO_TYPE.get(val)

    if isinstance(val, str):
        # Try to extract numeric code from parentheses first
        m = re.search(r"\((\d+)\)", val)
        if m:
            code = int(m.group(1))
            if code == 0:
                return None
            t = _TASMOTA_CODE_TO_TYPE.get(code)
            if t and t != "none":
                return t
        # Fallback: name-based resolution
        return _name_to_type(val)

    return None


def _parse_gpio_from_device(lines: list[str]) -> dict[int, str]:
    """
    Parse GPIO assignments from Tasmota serial responses.

    Handles all known Tasmota response formats:

    A. Bulk GPIO command (``GPIO`` without argument) – preferred:
       {"GPIO":{"0":"None (0)","32":"Relay1 (21)","33":"Relay2 (22)"}}
       Values are strings with optional "(code)" suffix.

    B. StatusGPIO (Status 13, Tasmota 12+):
       {"StatusGPIO":{"GPIO0":0,"GPIO32":21}}
       Values are numeric codes; keys are "GPIO<n>".

    C. Individual GPIOx query (``GPIO32``):
       {"GPIO32":"Relay1 (21)"}  or  {"GPIO32":21}
       One key per response line.

    Returns {gpio_num: type_id}, only non-None (assigned) pins.
    """
    result: dict[int, str] = {}

    # Tasmota 15 returns GPIO assignments in top-level keys like:
    #   "GPIO32":{"None":0}        → unassigned
    #   "GPIO32":{"Relay1":21}     → Relay1, code 21
    #   "GPIO12":{"Button10":41}   → Button10, code 41
    # This format appears in RESULT responses to GPIO / GPIOx commands,
    # as well as the older formats below.

    for line in lines:
        if '"GPIO' not in line:
            continue
        data = _extract_json(line)
        if not isinstance(data, dict):
            continue

        # --- A: Tasmota 15 style: top-level "GPIO<n>": {"FuncName": code} ----
        # Also handles old-style top-level "GPIO<n>": code  (int or string)
        for key, val in data.items():
            m = re.match(r"GPIO(\d+)$", key)
            if not m:
                continue
            gpio_num = int(m.group(1))

            if isinstance(val, dict):
                # New format: {"Relay1": 21} or {"None": 0}
                for func_name, code in val.items():
                    if func_name == "None" or code == 0:
                        continue
                    t = _to_type(code) or _name_to_type(func_name)
                    if t and t != "none":
                        result[gpio_num] = t
            else:
                # Old format: integer code or "Relay1 (21)" string
                t = _to_type(val)
                if t and t != "none":
                    result[gpio_num] = t

        # --- B: Bulk old-style {"GPIO": {"32": "Relay1 (21)", ...}} ----------
        if "GPIO" in data and isinstance(data["GPIO"], dict):
            for key, val in data["GPIO"].items():
                try:
                    gpio_num = int(key)
                except (ValueError, TypeError):
                    continue
                t = _to_type(val)
                if t and t != "none":
                    result[gpio_num] = t

        # --- C: StatusGPIO {"StatusGPIO": {"GPIO32": 21, ...}} ---------------
        if "StatusGPIO" in data and isinstance(data["StatusGPIO"], dict):
            for key, val in data["StatusGPIO"].items():
                m2 = re.match(r"GPIO(\d+)$", key)
                if not m2:
                    continue
                t = _to_type(val)
                if t and t != "none":
                    result[int(m2.group(1))] = t

    return result


# ---------------------------------------------------------------------------
# BoardDiagram widget – ASCII pin state map
# ---------------------------------------------------------------------------

class BoardDiagram(Static):
    """Renders an ASCII board diagram with live pin state colours."""

    def __init__(self, layout: BoardLayout, **kwargs):
        super().__init__("", **kwargs)
        self._layout = layout
        self._pin_states: dict[int, Optional[bool]] = {}
        self._gpio_functions: dict[int, str] = {}
        self._pwm_values: dict[int, int] = {}
        self._counter_values: dict[int, int] = {}

    def set_layout(self, layout: BoardLayout) -> None:
        self._layout = layout
        self.refresh_diagram()

    def set_pin_state(self, gpio: int, state: Optional[bool]) -> None:
        self._pin_states[gpio] = state
        self.refresh_diagram()

    def set_gpio_functions(self, assignments: dict[int, str]) -> None:
        self._gpio_functions = assignments
        self.refresh_diagram()

    def set_pwm_value(self, gpio: int, pct: int) -> None:
        self._pwm_values[gpio] = pct
        self.refresh_diagram()

    def set_counter_value(self, gpio: int, count: int) -> None:
        self._counter_values[gpio] = count
        self.refresh_diagram()

    def refresh_diagram(self) -> None:
        self.update(self._render_diagram())

    # ------------------------------------------------------------------

    def _pin_dot(self, pin: PinDef) -> str:
        if pin.is_power:
            return "[dim]●[/dim]"
        if pin.is_uart:
            return "[cyan]●[/cyan]"
        if pin.adc_only:
            return "[yellow]●[/yellow]"
        if pin.boot_sensitive:
            return "[orange3]●[/orange3]"
        if pin.gpio is not None:
            type_id = self._gpio_functions.get(pin.gpio)
            if type_id == "pwm" and pin.gpio in self._pwm_values:
                pct = self._pwm_values[pin.gpio]
                return "[bold cyan]■[/bold cyan]" if pct > 0 else "[dim]□[/dim]"
            if type_id == "counter" and pin.gpio in self._counter_values:
                cnt = self._counter_values[pin.gpio]
                return "[bold yellow]■[/bold yellow]" if cnt > 0 else "[dim]□[/dim]"
            state = self._pin_states.get(pin.gpio)
            if state is True:
                return "[bold green]■[/bold green]"
            elif state is False:
                return "[dim]□[/dim]"
        return "[dim]●[/dim]"

    def _pin_func_label(self, pin: PinDef) -> str:
        if pin.gpio is None:
            return ""
        type_id = self._gpio_functions.get(pin.gpio)
        if not type_id or type_id == "none":
            return "—"
        gt = GPIO_TYPE_BY_ID.get(type_id)
        label = gt.label if gt else type_id
        label = (label
                 .replace("Bemeneti érzékelő", "Bem.érz.")
                 .replace("Relé / Kapcsoló kimenet", "Relé kim.")
                 .replace("Nyomógomb (fizikai)", "Nyomógomb")
                 .replace("Impulzusszámláló", "Impulzussz.")
                 .replace("PWM fényerő szabályozás", "PWM")
                 .replace("Beépített státusz LED", "Státusz LED")
                 .replace("DHT22 / AM2301 – hőmérséklet + páratartalom", "DHT22")
                 .replace("DHT11 – hőmérséklet + páratartalom", "DHT11")
                 .replace("DS18B20 – hőmérséklet szenzor (1-Wire)", "DS18B20")
                 .replace("I2C busz – SCL (órajel)", "I2C SCL")
                 .replace("I2C busz – SDA (adat)", "I2C SDA"))
        return label[:14] if len(label) <= 14 else label[:13] + "…"

    def _state_text(self, pin: "PinDef") -> str:
        """Return the Rich-markup state string for a pin (5 chars wide)."""
        if pin.gpio is None:
            return "     "
        type_id = self._gpio_functions.get(pin.gpio)
        if type_id == "pwm" and pin.gpio in self._pwm_values:
            pct = self._pwm_values[pin.gpio]
            if pct > 0:
                label = f"{pct}%".rjust(4)
                return f"[cyan]■{label}[/cyan]"
            return "[dim]□  0%[/dim]"
        if type_id == "counter" and pin.gpio in self._counter_values:
            cnt = self._counter_values[pin.gpio]
            label = f"#{cnt}".rjust(4)
            return f"[yellow]■{label}[/yellow]" if cnt > 0 else f"[dim]□{label}[/dim]"
        state = self._pin_states.get(pin.gpio)
        if state is True:
            return "[green]■ ON [/green]"
        if state is False:
            return "[dim]□ OFF[/dim]"
        return "     "

    def _render_diagram(self) -> str:
        layout = self._layout
        w = layout.display_width

        left_pins  = sorted([p for p in layout.pins if p.side == "left"],  key=lambda x: x.row)
        right_pins = sorted([p for p in layout.pins if p.side == "right"], key=lambda x: x.row)
        rows = max(len(left_pins), len(right_pins))

        lines: list[str] = []
        lines.append(f"┌{'─' * (w - 2)}┐")
        lines.append(f"│{'   ' + layout.name:^{w - 2}}│")
        lines.append(f"│{'':^{w - 2}}│")

        for i in range(rows):
            lp = left_pins[i]  if i < len(left_pins)  else None
            rp = right_pins[i] if i < len(right_pins) else None

            if lp:
                l_dot   = self._pin_dot(lp)
                l_name  = f"{lp.label:<4}"
                l_func  = self._pin_func_label(lp)
                l_state = self._state_text(lp)
                left_part = f"{l_name} {l_dot} {l_func:<14} {l_state}"
            else:
                left_part = " " * 28

            if rp:
                r_dot   = self._pin_dot(rp)
                r_name  = f"{rp.label:<4}"
                r_func  = self._pin_func_label(rp)
                r_state = self._state_text(rp)
                right_part = f"{r_state} {r_func:<14} {r_dot} {r_name}"
            else:
                right_part = " " * 28

            lines.append(f"│ {left_part}  │  {right_part} │")

        lines.append(f"└{'─' * (w - 2)}┘")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# BoardTab
# ---------------------------------------------------------------------------

class BoardTab(TabPane):
    """Visual board pin state monitor with device info panel."""

    DEFAULT_CSS = ""

    # State
    _current_board: BoardLayout
    _pin_states: dict[int, Optional[bool]]
    _gpio_assignments: dict[int, str]

    # Device info
    _dev_hostname: str
    _dev_topic: str
    _dev_firmware: str
    _dev_hardware: str
    _dev_module_id: Optional[int]

    # WiFi
    _wifi_ssid: str
    _wifi_ip: str
    _wifi_rssi: Optional[int]

    # Sensor
    _sensor_data: dict[str, dict]
    _energy_data: dict

    # Uptime
    _uptime: str

    # Polling
    _polling: bool

    def compose(self) -> ComposeResult:
        with Vertical(id="board-tab"):
            # --- Controls row -------------------------------------------
            with Horizontal(id="board-controls"):
                yield Label("Board:", classes="label")
                yield Select(
                    options=[(b.name, b.name) for b in ALL_BOARDS],
                    value=D1_MINI.name,
                    id="board-type-select",
                    allow_blank=False,
                )
                yield Label("Forrás:", classes="label")
                with RadioSet(id="board-source-radio"):
                    yield RadioButton("MQTT", id="src-mqtt", value=True)
                    yield RadioButton("Serial", id="src-serial")
                yield Label("", id="board-uptime-label", classes="board-uptime")
                yield Button("↺ Lekérés", id="board-poll-btn", variant="primary")
                yield Button("GPIO diagn.", id="board-gpio-diag-btn", variant="default")

            # --- Main area: diagram (left) + info panel (right) ---------
            with Horizontal(id="board-main"):
                # Left: board diagram
                with ScrollableContainer(id="board-left-col"):
                    yield BoardDiagram(D1_MINI, id="board-diagram", markup=True)
                    # Pin table
                    with Vertical(id="board-pin-table"):
                        yield Static("Pin állapot", classes="section-title")
                        yield DataTable(
                            id="board-pin-datatable",
                            show_header=True,
                            classes="board-pin-table",
                        )

                # Right: info panel
                with ScrollableContainer(id="board-right-col"):
                    # --- Device info ------------------------------------
                    with Vertical(id="board-device-panel", classes="board-info-panel"):
                        yield Static("Eszköz", classes="section-title")
                        yield Label("–", id="board-dev-hostname")
                        yield Label("–", id="board-dev-topic")
                        yield Label("–", id="board-dev-firmware")
                        yield Label("–", id="board-dev-hardware")
                        yield Label("", id="board-dev-heap")

                    # --- WiFi -------------------------------------------
                    with Vertical(id="board-wifi-panel", classes="board-info-panel"):
                        yield Static("WiFi", classes="section-title")
                        yield Label("–", id="board-wifi-state")
                        yield Label("–", id="board-wifi-ssid")
                        yield Label("–", id="board-wifi-ip")
                        yield Label("–", id="board-wifi-signal")

                    # --- MQTT -------------------------------------------
                    with Vertical(id="board-mqtt-panel", classes="board-info-panel"):
                        yield Static("MQTT", classes="section-title")
                        yield Label("–", id="board-mqtt-broker")
                        yield Label("", id="board-mqtt-client")
                        yield Label("", id="board-mqtt-count")

                    # --- Outputs / command panel ------------------------
                    with Vertical(id="board-outputs-panel", classes="board-info-panel"):
                        yield Static("Kimenetek – vezérlés", classes="section-title")
                        yield Vertical(id="board-outputs-container")

                    # --- Sensor / Power ---------------------------------
                    with Vertical(id="board-sensor-panel", classes="board-info-panel"):
                        yield Static("Szenzor / Energiafogyasztás", classes="section-title")
                        yield Label("–", id="board-sensor-values")
                        yield Label("", id="board-energy-values")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        # Instance-level state init (avoid class-level mutable defaults)
        self._current_board    = D1_MINI
        self._pin_states       = {}
        self._gpio_assignments = {}
        self._dev_hostname     = ""
        self._dev_topic        = ""
        self._dev_firmware     = ""
        self._dev_hardware     = ""
        self._dev_module_id    = None
        self._dev_heap         = 0
        self._wifi_ssid        = ""
        self._wifi_ip          = ""
        self._wifi_rssi        = None
        self._mqtt_host        = ""
        self._mqtt_port        = 0
        self._mqtt_client      = ""
        self._mqtt_count       = 0
        self._sensor_data      = {}
        self._energy_data      = {}
        self._uptime              = ""
        self._polling             = False
        self._outputs_build_ver   = 0

        self._pin_table_keys: dict[int, str] = {}   # gpio_num → row_key
        self._outputs_signature: tuple = ()          # snapshot of current outputs structure
        self._pwm_values: dict[int, int] = {}        # gpio_num → duty cycle 0-100
        self._counter_values: dict[int, int] = {}    # gpio_num → pulse count
        # Track our own TX relay/power commands so we don't misidentify their
        # echo as a physical switch press (key: "POWER{n}", value: expiry monotonic)
        self._sent_power_cmds: dict[str, float] = {}

        table: DataTable = self.query_one("#board-pin-datatable")
        table.add_column("Pin",    key="pin")
        table.add_column("GPIO",   key="gpio")
        table.add_column("Funkció",key="func")
        table.add_column("Irány",  key="dir")
        table.add_column("Állapot",key="state")
        self._rebuild_pin_table()
        self._rebuild_outputs_panel()

        self.run_worker(self._mqtt_state_listener(),    exclusive=True,  name="board_mqtt")
        self.run_worker(self._auto_poll_serial(),       exclusive=True,  name="board_serial_poll")
        self.run_worker(self._chip_watcher(),           exclusive=False, name="board_chip_watcher")
        self.run_worker(self._serial_state_monitor(),   exclusive=False, name="board_serial_live")

    # ------------------------------------------------------------------
    # Select / button handlers
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "board-type-select" and event.value is not Select.BLANK:
            board = BOARD_BY_NAME.get(str(event.value), D1_MINI)
            self._current_board = board
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_layout(board)
            diag.set_gpio_functions(self._gpio_assignments)
            self._rebuild_pin_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "board-poll-btn":
            self.run_worker(self._poll_device(), name="board_manual_poll")
        elif bid == "board-gpio-diag-btn":
            self.run_worker(self._gpio_diagnostics(), name="board_gpio_diag")
        elif bid.startswith("bout_"):
            # Relay/LED: bout_{on|off|toggle}_{gpio}  e.g. bout_on_32
            # PWM:       bout_pwm_set_{gpio}
            if bid.startswith("bout_pwm_set_"):
                gpio_str = bid[len("bout_pwm_set_"):]
                try:
                    self._send_output_command(int(gpio_str), "pwm_set")
                except ValueError:
                    pass
            else:
                parts = bid.split("_", 2)
                if len(parts) == 3:
                    action, gpio_str = parts[1], parts[2]
                    try:
                        self._send_output_command(int(gpio_str), action)
                    except ValueError:
                        pass

    # ------------------------------------------------------------------
    # Background workers
    # ------------------------------------------------------------------

    async def _chip_watcher(self) -> None:
        """Auto-select board type when chip is detected via serial."""
        from tasmota_manager.board_layouts import CHIP_DEFAULT_BOARD
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        last_chip: Optional[str] = None
        while True:
            chip = serial_bridge.detected_chip
            if chip and chip != last_chip:
                last_chip = chip
                board_name = CHIP_DEFAULT_BOARD.get(chip)
                if board_name and board_name in BOARD_BY_NAME:
                    sel: Select = self.query_one("#board-type-select")
                    sel.value = board_name
                    self._current_board = BOARD_BY_NAME[board_name]
                    diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
                    diag.set_layout(self._current_board)
                    self._rebuild_pin_table()
            await asyncio.sleep(1.0)

    async def _auto_poll_serial(self) -> None:
        """Auto-poll device state every 10 s when Serial source is selected."""
        while True:
            await asyncio.sleep(10)
            rs: RadioSet = self.query_one("#board-source-radio")
            if rs.pressed_index == 1:
                await self._poll_device()

    async def _serial_state_monitor(self) -> None:
        """Real-time state-line monitor: apply POWER/Switch/Sensor state changes.

        Works with both serial and HTTP bridges: reads from whichever bridge's
        state_queue is currently active.  For HTTP the queue is populated each
        time send_cmd() returns a response (request/response model), so live
        updates from physical button presses require the auto-poll to be active.
        """
        _POWER_RE = re.compile(r"POWER(\d*)\s*=\s*(ON|OFF)", re.IGNORECASE)
        _RESULT_POWER_RE = re.compile(r'"POWER(\d*)"\s*:\s*"(ON|OFF)"', re.IGNORECASE)
        _SWITCH_RE = re.compile(r'"Switch(\d+)"\s*:\s*"(ON|OFF)"', re.IGNORECASE)
        # COUNTER in tele/SENSOR or STATUS10: "COUNTER":{"C1":1251}
        _COUNTER_RE = re.compile(r'"C(\d+)"\s*:\s*(\d+)')

        # Debounce: after a device-initiated POWER event (from a physical switch press),
        # query Status 10 once so the switch GPIO's own state also refreshes.
        # We only do this for TX-less events and at most once per 2 seconds.
        _last_switch_poll: float = 0.0

        while True:
            app = self.app  # type: ignore[attr-defined]
            if app.http_bridge.is_connected:
                active_queue = app.http_bridge.state_queue
            elif app.serial_bridge.is_connected:
                active_queue = app.serial_bridge.state_queue
            else:
                await asyncio.sleep(0.5)
                continue
            try:
                line = await asyncio.wait_for(active_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.5)
                continue

            power_hit = False

            # Relay state: stat/.../POWER1 = ON  (direct topic message)
            for m in _POWER_RE.finditer(line):
                idx = int(m.group(1) or "1")
                state = m.group(2).upper() == "ON"
                power_key = f"POWER{idx}"
                our_echo = (
                    self._sent_power_cmds.get(power_key, 0) > _time_module.monotonic()
                )

                if our_echo:
                    # Our own command echo → update relay GPIO state immediately.
                    gpio = self._find_gpio_for_relay(idx)
                    if gpio is not None:
                        self._set_pin(gpio, state)
                else:
                    # Device-initiated event (physical switch press):
                    # → only update the switch input GPIO, NOT the relay output.
                    #   The relay state will be corrected on the next Status 11 poll.
                    # → flip the switch GPIO optimistically; Status 10 query below
                    #   will confirm the real physical state within 1 second.
                    sw_gpio = self._find_gpio_for_switch(idx)
                    if sw_gpio is not None:
                        current = self._pin_states.get(sw_gpio)
                        self._set_pin(sw_gpio, not current if current is not None else True)
                    power_hit = True

            # RESULT JSON on serial: {"POWER1":"ON"} or {"Switch1":"ON"}
            # Skip STATUS11 lines – they also contain "POWER1":"ON" but are periodic
            # poll responses, not device-initiated events.
            if "STATUS11" not in line and "StatusSTS" not in line:
                for m in _RESULT_POWER_RE.finditer(line):
                    idx = int(m.group(1) or "1")
                    state = m.group(2).upper() == "ON"
                    power_key = f"POWER{idx}"
                    our_echo = (
                        self._sent_power_cmds.get(power_key, 0) > _time_module.monotonic()
                    )
                    if our_echo:
                        gpio = self._find_gpio_for_relay(idx)
                        if gpio is not None:
                            self._set_pin(gpio, state)
                    # Switch flip is already done by the direct POWER topic handler above.

            # Switch state directly in serial (e.g. from tele/SENSOR or STATUS10)
            for m in _SWITCH_RE.finditer(line):
                inst = int(m.group(1))
                state = m.group(2).upper() == "ON"
                gpio = self._find_gpio_for_switch(inst)
                if gpio is not None:
                    self._set_pin(gpio, state)

            # Counter values from SENSOR/STATUS10: "COUNTER":{"C1":1251}
            # Only parse lines that contain the COUNTER key to avoid false matches
            if '"COUNTER"' in line:
                for m in _COUNTER_RE.finditer(line):
                    inst = int(m.group(1))
                    count = int(m.group(2))
                    gpio = self._find_gpio_for_type("counter", inst)
                    if gpio is not None:
                        self._set_counter_value(gpio, count)

            # After a POWER event, send Status 10 to confirm the actual switch states
            # (debounced: max once per second to avoid spamming the device)
            if power_hit and self._find_gpio_for_switch(1) is not None:
                now = _time_module.monotonic()
                if now - _last_switch_poll >= 1.0:
                    _last_switch_poll = now
                    self.app.send_cmd("Status 10")  # type: ignore[attr-defined]

    async def _mqtt_state_listener(self) -> None:
        """Consume MQTT tele/STATE and tele/SENSOR messages."""
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        while True:
            try:
                msg = await asyncio.wait_for(mqtt_mgr.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.5)
                continue
            # Re-put so MQTT monitor tab can also read it
            mqtt_mgr.queue.put_nowait(msg)
            cmd = msg.command or ""
            if cmd == "STATE":
                self._apply_state(msg.payload_json)
            elif cmd == "SENSOR":
                self._apply_sensor(msg.payload_json)
            elif cmd == "RESULT":
                # RESULT carries both relay power and switch state changes
                self._apply_result(msg.payload_json)
            elif re.match(r"POWER\d*$", cmd):
                # Direct stat/.../POWER1 = ON/OFF topic
                idx = int(cmd[5:]) if cmd[5:].isdigit() else 1
                payload_str = str(msg.payload_json or msg.payload or "")
                self._apply_power(idx, payload_str.strip().upper() == "ON")

    # ------------------------------------------------------------------
    # Serial polling
    # ------------------------------------------------------------------

    async def _poll_device(self) -> None:
        """Send Status queries + individual GPIOx commands to get full device state."""
        app = self.app  # type: ignore[attr-defined]
        bridge = app.http_bridge if app.http_bridge.is_connected else app.serial_bridge
        if self._polling:
            return
        if not bridge.is_connected:
            self.notify("Nincs kapcsolat! (Serial tab → Csatlakozás / HTTP)",
                        severity="warning", timeout=5)
            return
        self._polling = True
        btn: Button = self.query_one("#board-poll-btn")
        btn.disabled = True
        btn.label = "Lekérés…"
        try:
            bridge.clear_buffer()

            # Phase 1: standard Status queries
            for cmd, delay in [
                ("Status 1",  0.5),   # topic, hostname
                ("Status 2",  0.5),   # firmware, hardware
                ("Status 4",  0.5),   # memory / heap
                ("Status 5",  0.6),   # WiFi IP/SSID/RSSI
                ("Status 6",  0.5),   # MQTT broker info
                ("Status 10", 0.6),   # sensors + energy
                ("Status 11", 0.6),   # GPIO states, uptime
            ]:
                app.send_cmd(cmd)
                await asyncio.sleep(delay)

            # Phase 2: bulk GPIO assignment query
            # "GPIO" (no argument) returns all current GPIO assignments at once.
            # Falls back to individual GPIOx queries if bulk returns nothing.
            btn.label = "GPIO…"
            app.send_cmd("GPIO")
            await asyncio.sleep(0.8)   # wait for bulk response

            lines = list(bridge.line_buffer)
            self._apply_status1(_parse_status1(lines))
            self._apply_status2(_parse_status2(lines))
            self._apply_status4(_parse_status4(lines))
            self._apply_status5(_parse_status5(lines))
            self._apply_status6(_parse_status6(lines))
            self._apply_status10(_parse_status10(lines))
            self._apply_status11(_parse_status11(lines))

            # GPIO assignments from individual GPIOx responses
            gpio_from_device = _parse_gpio_from_device(lines)
            if gpio_from_device:
                self.update_gpio_assignments(gpio_from_device, from_device=True)
                summary = ", ".join(
                    f"GPIO{g}={t}" for g, t in sorted(gpio_from_device.items())
                )
                self.notify(
                    f"GPIO az eszközről ({len(gpio_from_device)} pin): {summary}",
                    severity="information", timeout=5,
                )
            else:
                # Fallback: individual GPIOx queries for each board pin
                btn.label = "GPIO…"
                board_gpio_nums = [
                    pin.gpio for pin in self._current_board.pins
                    if pin.gpio is not None and not pin.is_power and not pin.is_uart
                ]
                bridge.clear_buffer()
                for gpio_num in board_gpio_nums:
                    app.send_cmd(f"GPIO{gpio_num}")
                    await asyncio.sleep(0.1)
                await asyncio.sleep(0.5)
                lines2 = list(bridge.line_buffer)
                gpio_from_device2 = _parse_gpio_from_device(lines2)
                if gpio_from_device2:
                    self.update_gpio_assignments(gpio_from_device2, from_device=True)
                    summary = ", ".join(
                        f"GPIO{g}={t}" for g, t in sorted(gpio_from_device2.items())
                    )
                    self.notify(
                        f"GPIO az eszközről ({len(gpio_from_device2)} pin): {summary}",
                        severity="information", timeout=5,
                    )
                else:
                    self.notify(
                        "Nincs konfigurált GPIO az eszközön\n"
                        "Ellenőrizd a Serial tabban: GPIO parancs eredménye",
                        severity="warning", timeout=6,
                    )
        except Exception:
            pass
        finally:
            self._polling = False
            btn.disabled = False
            btn.label = "↺ Lekérés"

    # ------------------------------------------------------------------
    # Apply parsed data → update state + UI
    # ------------------------------------------------------------------

    def _apply_status1(self, data: dict) -> None:
        if data.get("hostname"):
            self._dev_hostname = data["hostname"]
        if data.get("topic"):
            self._dev_topic = data["topic"]
        if data.get("module_id") is not None:
            self._dev_module_id = int(data["module_id"])
        self._update_device_panel()

    def _apply_status2(self, data: dict) -> None:
        if data.get("firmware"):
            self._dev_firmware = data["firmware"]
        if data.get("hardware"):
            self._dev_hardware = data["hardware"]
        self._update_device_panel()

    def _apply_status4(self, data: dict) -> None:
        if data.get("heap"):
            self._dev_heap = data["heap"]
            self._update_device_panel()

    def _apply_status5(self, data: dict) -> None:
        if data.get("ssid"):
            self._wifi_ssid = data["ssid"]
        if data.get("ip"):
            self._wifi_ip = data["ip"]
        if data.get("rssi") is not None:
            self._wifi_rssi = data["rssi"]
        self._update_wifi_panel()

    def _apply_status6(self, data: dict) -> None:
        if data.get("mqtt_host"):
            self._mqtt_host = str(data["mqtt_host"])
        if data.get("mqtt_port"):
            self._mqtt_port = int(data["mqtt_port"])
        if data.get("mqtt_client"):
            self._mqtt_client = str(data["mqtt_client"])
        if data.get("mqtt_count") is not None:
            self._mqtt_count = int(data["mqtt_count"])
        self._update_mqtt_panel()

    def _apply_status10(self, data: dict) -> None:
        if data.get("sensors"):
            self._sensor_data = data["sensors"]
        if data.get("energy"):
            self._energy_data = data["energy"]
        for inst, state in data.get("switches", {}).items():
            gpio = self._find_gpio_for_switch(inst)
            if gpio is not None:
                self._set_pin(gpio, state)
        for inst, count in data.get("counters", {}).items():
            gpio = self._find_gpio_for_type("counter", inst)
            if gpio is not None:
                self._set_counter_value(gpio, count)
        self._update_sensor_panel()

    def _apply_status11(self, data: dict) -> None:
        if data.get("uptime"):
            self._uptime = data["uptime"]
            uptime_lbl: Label = self.query_one("#board-uptime-label")
            uptime_lbl.update(f"[dim]Uptime:[/dim] {self._uptime}")
        if data.get("wifi_rssi") is not None:
            self._wifi_rssi = data["wifi_rssi"]
            self._update_wifi_panel()
        for idx, state in data.get("power", {}).items():
            gpio = self._find_gpio_for_relay(idx)
            if gpio is not None:
                self._set_pin(gpio, state)
        for inst, pct in data.get("pwm", {}).items():
            gpio = self._find_gpio_for_type("pwm", inst)
            if gpio is not None:
                self._set_pwm_value(gpio, pct)

    # ------------------------------------------------------------------
    # Apply MQTT payloads
    # ------------------------------------------------------------------

    def _apply_state(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        for key, val in payload.items():
            m = re.match(r"POWER(\d*)", key)
            if m:
                idx = int(m.group(1) or "1")
                gpio = self._find_gpio_for_relay(idx)
                if gpio is not None:
                    self._set_pin(gpio, val == "ON")
        wifi = payload.get("Wifi", {})
        if isinstance(wifi, dict):
            sig = wifi.get("Signal")
            rssi_pct = wifi.get("RSSI")
            if sig is not None:
                try:
                    self._wifi_rssi = int(sig)
                except ValueError:
                    pass
            elif rssi_pct is not None:
                try:
                    pct = int(rssi_pct)
                    self._wifi_rssi = pct if pct < 0 else pct // 2 - 100
                except ValueError:
                    pass
            self._update_wifi_panel()
        uptime = payload.get("Uptime", "")
        if uptime:
            self._uptime = str(uptime)
            try:
                self.query_one("#board-uptime-label").update(
                    f"[dim]Uptime:[/dim] {self._uptime}"
                )
            except Exception:
                pass
        # PWM Channel array: [pct0, pct1, ...] in tele/STATE
        channels = payload.get("Channel")
        if isinstance(channels, list):
            for i, pct in enumerate(channels):
                gpio = self._find_gpio_for_type("pwm", i + 1)
                if gpio is not None:
                    try:
                        self._set_pwm_value(gpio, int(pct))
                    except (TypeError, ValueError):
                        pass

    def _apply_result(self, payload: object) -> None:
        """Handle stat/.../RESULT messages: relay POWER states + switch states."""
        if not isinstance(payload, dict):
            return
        for key, val in payload.items():
            # POWER1, POWER2, ... → relay / PWM on-off state
            m = re.match(r"POWER(\d*)$", key)
            if m:
                idx = int(m.group(1) or "1")
                gpio = self._find_gpio_for_relay(idx)
                if gpio is not None:
                    self._set_pin(gpio, val == "ON")
            # Switch1, Switch2, ... → switch input state
            m2 = re.match(r"Switch(\d+)$", key)
            if m2:
                gpio = self._find_gpio_for_switch(int(m2.group(1)))
                if gpio is not None:
                    self._set_pin(gpio, val == "ON")
            # Dimmer (single channel) or Dimmer1/2/...
            m3 = re.match(r"Dimmer(\d*)$", key)
            if m3:
                inst = int(m3.group(1) or "1")
                gpio = self._find_gpio_for_type("pwm", inst)
                if gpio is not None:
                    try:
                        self._set_pwm_value(gpio, int(val))
                    except (TypeError, ValueError):
                        pass
        # Channel array in RESULT (e.g. after Dimmer command)
        channels = payload.get("Channel")
        if isinstance(channels, list):
            for i, pct in enumerate(channels):
                gpio = self._find_gpio_for_type("pwm", i + 1)
                if gpio is not None:
                    try:
                        self._set_pwm_value(gpio, int(pct))
                    except (TypeError, ValueError):
                        pass

    def _apply_power(self, idx: int, state: bool) -> None:
        """Handle stat/.../POWER{n} = ON|OFF direct topic messages."""
        gpio = self._find_gpio_for_relay(idx)
        if gpio is not None:
            self._set_pin(gpio, state)

    def _apply_sensor(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        _SENSOR_KEYS = {"AM2301", "DHT11", "DHT22", "DS18B20", "BMP280",
                        "BME280", "BME680", "SHT3X", "AHT20", "SCD40",
                        "SI7021", "HTU21", "MCP9808", "TSL2561"}
        for key, val in payload.items():
            m = re.match(r"Switch(\d+)", key)
            if m:
                gpio = self._find_gpio_for_switch(int(m.group(1)))
                if gpio is not None:
                    self._set_pin(gpio, val == "ON")
            if key in _SENSOR_KEYS and isinstance(val, dict):
                self._sensor_data[key] = val
            if key == "ENERGY" and isinstance(val, dict):
                self._energy_data = val
            # COUNTER.C1, C2, ... nested format from tele/SENSOR
            if key == "COUNTER" and isinstance(val, dict):
                for ck, cv in val.items():
                    cm = re.match(r"C(\d+)$", ck)
                    if cm:
                        gpio = self._find_gpio_for_type("counter", int(cm.group(1)))
                        if gpio is not None:
                            try:
                                self._set_counter_value(gpio, int(cv))
                            except (TypeError, ValueError):
                                pass
        self._update_sensor_panel()

    # ------------------------------------------------------------------
    # Pin state helpers
    # ------------------------------------------------------------------

    def _set_pin(self, gpio: int, state: Optional[bool]) -> None:
        self._pin_states[gpio] = state
        try:
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_pin_state(gpio, state)
        except Exception:
            pass
        self._rebuild_pin_table()
        self._update_output_state_label(gpio)

    def _set_pwm_value(self, gpio: int, pct: int) -> None:
        """Store and display a PWM duty cycle value (0-100) for the given GPIO."""
        self._pwm_values[gpio] = pct

        # Update pin state (ON if duty > 0) so the pin table refreshes too
        self._set_pin(gpio, pct > 0)

        # Also push the PWM value to the board diagram for % display
        try:
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_pwm_value(gpio, pct)
        except Exception:
            pass

        try:
            inp: Input = self.query_one(f"#bout_pwm_input_{gpio}", Input)
            inp.value = str(pct)
        except Exception:
            pass
        try:
            lbl: Label = self.query_one(f"#bout_pwm_lbl_{gpio}", Label)
            type_id = self._gpio_assignments.get(gpio, "pwm")
            gt = GPIO_TYPE_BY_ID.get(type_id)
            short = (gt.label if gt else "PWM").replace("PWM fényerő szabályozás", "PWM")
            board = self._current_board
            d_alias = board.gpio_to_dpin.get(gpio, "")
            pin_name = f"{d_alias}/{gpio}" if d_alias else f"GPIO{gpio}"
            lbl.update(f"{short}  [dim]({pin_name})[/dim]  [bold cyan]{pct}%[/bold cyan]")
        except Exception:
            pass

    def _set_counter_value(self, gpio: int, count: int) -> None:
        """Store and display a pulse counter value for the given GPIO."""
        self._counter_values[gpio] = count
        self._set_pin(gpio, count > 0)   # refreshes pin table row
        try:
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_counter_value(gpio, count)
        except Exception:
            pass

    def _find_gpio_for_relay(self, instance: int) -> Optional[int]:
        return self._find_gpio_for_type("relay", instance)

    def _find_gpio_for_switch(self, instance: int) -> Optional[int]:
        return self._find_gpio_for_type("switch", instance)

    def _find_gpio_for_type(self, type_id: str, instance: int) -> Optional[int]:
        counter = 0
        for gpio in sorted(self._gpio_assignments):
            if self._gpio_assignments[gpio] == type_id:
                counter += 1
                if counter == instance:
                    return gpio
        return None

    # ------------------------------------------------------------------
    # GPIO assignments sync (called from app)
    # ------------------------------------------------------------------

    def update_gpio_assignments(self, assignments: dict[int, str],
                                from_device: bool = False) -> None:
        """Update GPIO assignments.

        from_device=True  → always apply (device is authoritative).
        from_device=False → only apply if no device data has been loaded yet,
                            so a previous Status 13 result is not overwritten.
        """
        if not from_device and self._gpio_assignments:
            return   # device data already present – don't overwrite with Config tab data
        self._gpio_assignments = assignments
        try:
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_gpio_functions(assignments)
        except Exception:
            pass
        self._rebuild_pin_table()
        self._rebuild_outputs_panel()

    def clear_device_data(self) -> None:
        """Reset all device-specific state (called when a new serial connection is made)."""
        self._gpio_assignments = {}
        self._pin_states       = {}
        self._pwm_values       = {}
        self._counter_values   = {}
        self._sent_power_cmds  = {}
        self._dev_hostname     = ""
        self._dev_topic        = ""
        self._dev_firmware     = ""
        self._dev_hardware     = ""
        self._dev_module_id    = None
        self._dev_heap         = 0
        self._wifi_ssid        = ""
        self._wifi_ip          = ""
        self._wifi_rssi        = None
        self._mqtt_host        = ""
        self._mqtt_port        = 0
        self._mqtt_client      = ""
        self._mqtt_count       = 0
        self._sensor_data      = {}
        self._energy_data      = {}
        self._uptime           = ""
        # Clear diagram
        try:
            diag: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diag.set_gpio_functions({})
            diag._pwm_values    = {}
            diag._counter_values = {}
            diag._pin_states    = {}
        except Exception:
            pass
        # Clear pin table
        try:
            table: DataTable = self.query_one("#board-pin-datatable")
            table.clear()
            self._pin_table_keys = {}
        except Exception:
            pass
        # Rebuild empty outputs panel
        self._outputs_signature = ()
        self._rebuild_outputs_panel()
        # Clear device info labels
        self._update_device_panel()
        self._update_wifi_panel()
        self._update_mqtt_panel()
        self._update_sensor_panel()

    # ------------------------------------------------------------------
    # Pin table rebuild
    # ------------------------------------------------------------------

    def _rebuild_pin_table(self) -> None:
        """Rebuild pin table in-place: add/update rows without flickering clear()."""
        try:
            table: DataTable = self.query_one("#board-pin-datatable")
        except Exception:
            return
        board = self._current_board

        current_gpios = {
            pin.gpio for pin in board.pins if pin.gpio is not None
        }

        # Remove rows for GPIOs no longer on this board
        for gpio in list(self._pin_table_keys):
            if gpio not in current_gpios:
                try:
                    table.remove_row(self._pin_table_keys.pop(gpio))
                except Exception:
                    pass

        for pin in sorted(board.pins, key=lambda p: (p.side, p.row)):
            if pin.gpio is None:
                continue

            type_id   = self._gpio_assignments.get(pin.gpio)
            gt        = GPIO_TYPE_BY_ID.get(type_id or "none")
            func_lbl  = gt.label if (gt and type_id and type_id != "none") else "—"
            direction = gt.direction if (gt and type_id and type_id != "none") else "–"

            state = self._pin_states.get(pin.gpio)
            d_alias   = board.gpio_to_dpin.get(pin.gpio, "")
            pin_label = f"{d_alias} / GPIO{pin.gpio}" if d_alias else f"GPIO{pin.gpio}"
            if pin.boot_sensitive:
                pin_label += " ⚠"

            # For PWM pins show duty cycle percentage instead of plain ON/OFF
            is_pwm = (type_id == "pwm")
            if is_pwm and pin.gpio in self._pwm_values:
                pct = self._pwm_values[pin.gpio]
                if pct > 0:
                    state_text = Text(f"■ {pct}%", style="bold cyan")
                else:
                    state_text = Text("□ 0%", style="dim")
            # For counter pins show the current pulse count
            elif type_id == "counter" and pin.gpio in self._counter_values:
                cnt = self._counter_values[pin.gpio]
                state_text = Text(f"# {cnt}", style="bold yellow" if cnt > 0 else "dim")
            elif state is True:
                state_text = Text("■ ON",  style="bold green")
            elif state is False:
                state_text = Text("□ OFF", style="dim")
            else:
                state_text = Text("–",     style="dim")

            row_key = f"gpio{pin.gpio}"
            if pin.gpio not in self._pin_table_keys:
                # New row – add it
                table.add_row(pin_label, f"GPIO{pin.gpio}", func_lbl, direction,
                              state_text, key=row_key)
                self._pin_table_keys[pin.gpio] = row_key
            else:
                # Existing row – update cells in-place (no flicker)
                try:
                    table.update_cell(row_key, "func",  func_lbl,  update_width=False)
                    table.update_cell(row_key, "dir",   direction, update_width=False)
                    table.update_cell(row_key, "state", state_text,update_width=False)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Outputs panel – dynamic command buttons
    # ------------------------------------------------------------------

    def _rebuild_outputs_panel(self) -> None:
        """Rebuild output controls, or just refresh state labels if structure unchanged."""
        # Compute the current outputs signature (sorted list of (gpio, type_id))
        new_sig: tuple = tuple(
            (gpio, t)
            for gpio in sorted(self._gpio_assignments)
            if (t := self._gpio_assignments[gpio]) in _OUTPUT_CMD
        )

        if new_sig == self._outputs_signature:
            # Structure unchanged – only update state labels in-place
            for gpio, type_id, _ in self._outputs_from_signature(new_sig):
                if type_id in ("relay", "led"):
                    self._update_output_state_label(gpio)
            return

        # Structure changed – full rebuild
        self._outputs_signature = new_sig
        self._outputs_build_ver += 1
        ver = self._outputs_build_ver
        self.call_after_refresh(self._do_rebuild_outputs, ver)

    @staticmethod
    def _outputs_from_signature(sig: tuple) -> list[tuple[int, str, int]]:
        """Convert signature to (gpio, type_id, instance_num) list."""
        result = []
        counters: dict[str, int] = {}
        for gpio, type_id in sig:
            counters[type_id] = counters.get(type_id, 0) + 1
            result.append((gpio, type_id, counters[type_id]))
        return result

    def _do_rebuild_outputs(self, ver: int) -> None:
        if ver != self._outputs_build_ver:
            return
        try:
            container = self.query_one("#board-outputs-container", Vertical)
        except Exception:
            return

        # Remove old rows
        for child in list(container.children):
            child.remove()

        outputs = self._outputs_from_signature(self._outputs_signature)

        if not outputs:
            container.mount(Label("[dim]Nincs konfigurált kimenet[/dim]",
                                  classes="board-output-empty"))
            return

        for gpio, type_id, inst in outputs:
            gt = GPIO_TYPE_BY_ID.get(type_id)
            label_text = gt.label if gt else type_id
            short = (label_text
                     .replace("Relé / Kapcsoló kimenet", "Relé")
                     .replace("PWM fényerő szabályozás", "PWM")
                     .replace("Beépített státusz LED", "LED"))
            board = self._current_board
            d_alias = board.gpio_to_dpin.get(gpio, "")
            pin_name = f"{d_alias}/{gpio}" if d_alias else f"GPIO{gpio}"

            state = self._pin_states.get(gpio)
            if state is True:
                state_markup = "[bold green]■ ON [/bold green]"
            elif state is False:
                state_markup = "[dim]□ OFF[/dim]"
            else:
                state_markup = "[dim]  –  [/dim]"

            row = Horizontal(classes="board-output-row")

            if type_id in ("relay", "led"):
                name_label = Label(
                    f"{short} {inst}  [dim]({pin_name})[/dim]  {state_markup}",
                    classes="board-output-name",
                    id=f"bout_state_lbl_{gpio}",
                )
                btn_on     = Button("BE",     id=f"bout_on_{gpio}",     variant="success", classes="board-output-btn")
                btn_off    = Button("KI",     id=f"bout_off_{gpio}",    variant="error",   classes="board-output-btn")
                btn_toggle = Button("VÁLTÁS", id=f"bout_toggle_{gpio}", variant="default", classes="board-output-btn")
                row.compose_add_child(name_label)
                row.compose_add_child(btn_on)
                row.compose_add_child(btn_off)
                row.compose_add_child(btn_toggle)

            elif type_id == "pwm":
                current_pct = self._pwm_values.get(gpio)
                pct_markup = (f"  [bold cyan]{current_pct}%[/bold cyan]"
                              if current_pct is not None else "")
                name_label = Label(
                    f"{short} {inst}  [dim]({pin_name})[/dim]{pct_markup}",
                    classes="board-output-name",
                    id=f"bout_pwm_lbl_{gpio}",
                )
                pwm_input = Input(
                    value=str(current_pct) if current_pct is not None else "",
                    placeholder="0–100",
                    id=f"bout_pwm_input_{gpio}",
                    classes="board-output-pwm-input",
                )
                btn_set = Button("Beállít", id=f"bout_pwm_set_{gpio}", variant="primary", classes="board-output-btn")
                row.compose_add_child(name_label)
                row.compose_add_child(pwm_input)
                row.compose_add_child(btn_set)

            container.mount(row)

    def _update_output_state_label(self, gpio: int) -> None:
        """Refresh the state markup in an output row label after state change."""
        try:
            lbl: Label = self.query_one(f"#bout_state_lbl_{gpio}", Label)
        except Exception:
            return
        type_id = self._gpio_assignments.get(gpio, "")
        state = self._pin_states.get(gpio)
        gt = GPIO_TYPE_BY_ID.get(type_id)
        label_text = (gt.label if gt else type_id)
        short = (label_text
                 .replace("Relé / Kapcsoló kimenet", "Relé")
                 .replace("Beépített státusz LED", "LED"))
        # Count instance number
        inst = 1
        cnt = 0
        for g in sorted(self._gpio_assignments):
            if self._gpio_assignments[g] == type_id:
                cnt += 1
                if g == gpio:
                    inst = cnt
                    break
        board = self._current_board
        d_alias = board.gpio_to_dpin.get(gpio, "")
        pin_name = f"{d_alias}/{gpio}" if d_alias else f"GPIO{gpio}"
        if state is True:
            state_markup = "[bold green]■ ON [/bold green]"
        elif state is False:
            state_markup = "[dim]□ OFF[/dim]"
        else:
            state_markup = "[dim]  –  [/dim]"
        lbl.update(f"{short} {inst}  [dim]({pin_name})[/dim]  {state_markup}")

    # ------------------------------------------------------------------
    # Send output command (serial or MQTT)
    # ------------------------------------------------------------------

    def _send_output_command(self, gpio: int, action: str) -> None:
        """Send a relay/PWM command via serial or MQTT."""
        type_id = self._gpio_assignments.get(gpio)
        if not type_id or type_id not in _OUTPUT_CMD:
            return

        cmd_prefix = _OUTPUT_CMD[type_id]

        # Compute instance number for this gpio
        inst = 1
        cnt = 0
        for g in sorted(self._gpio_assignments):
            if self._gpio_assignments[g] == type_id:
                cnt += 1
                if g == gpio:
                    inst = cnt
                    break

        # Handle PWM set (action = "pwm_set_{gpio}")
        if action == "pwm_set":
            try:
                inp: Input = self.query_one(f"#bout_pwm_input_{gpio}", Input)
                value = inp.value.strip()
                if not value.isdigit():
                    self.notify("Érvénytelen PWM érték (0–100)!", severity="warning")
                    return
                v = max(0, min(100, int(value)))
                cmd   = f"Dimmer{inst}"
                payload = str(v)
                # Optimistically update displayed value before device confirms
                self._set_pwm_value(gpio, v)
            except Exception:
                return
        else:
            action_map = {"on": "ON", "off": "OFF", "toggle": "TOGGLE"}
            payload = action_map.get(action)
            if not payload:
                return
            cmd = f"{cmd_prefix}{inst}"

        self._dispatch_command(cmd, payload)

    def _dispatch_command(self, cmd: str, value: str) -> None:
        """Route command to serial or MQTT based on the source radio."""
        try:
            rs: RadioSet = self.query_one("#board-source-radio")
            use_serial = (rs.pressed_index == 1)
        except Exception:
            use_serial = True

        sent = False
        if not use_serial:
            mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
            topic = self._dev_topic
            if mqtt_mgr.connected and topic:
                mqtt_mgr.publish(f"cmnd/{topic}/{cmd}", value)
                self.notify(f"MQTT → cmnd/{topic}/{cmd}  {value}", severity="information")
                sent = True

        if not sent:
            app = self.app  # type: ignore[attr-defined]
            if app.serial_bridge.is_connected or app.http_bridge.is_connected:
                app.send_cmd(f"{cmd} {value}")
                conn_type = "HTTP" if app.http_bridge.is_connected else "Serial"
                self.notify(f"{conn_type} → {cmd} {value}", severity="information")
                sent = True
            else:
                self.notify(
                    "Nincs kapcsolat! (Serial tab → Csatlakozás / HTTP)",
                    severity="error", timeout=5,
                )
                return

        # For relay/LED commands: re-query Status 11 after short delay to confirm state
        if sent and cmd.upper().startswith("POWER"):
            self.run_worker(self._verify_relay_state(), name="board_relay_verify")
            # Mark this POWER index as "sent by us" for the next 3 s so the state
            # monitor won't mistake the device echo for a physical switch press.
            key = cmd.upper()   # e.g. "POWER1"
            self._sent_power_cmds[key] = _time_module.monotonic() + 3.0

    async def _gpio_diagnostics(self) -> None:
        """Send GPIO command and show raw response lines in a notification."""
        app = self.app  # type: ignore[attr-defined]
        bridge = app.http_bridge if app.http_bridge.is_connected else app.serial_bridge
        if not bridge.is_connected:
            self.notify("Nincs kapcsolat!", severity="warning")
            return

        bridge.clear_buffer()
        # Try both the bulk GPIO command and GPIO32 individually
        app.send_cmd("GPIO")
        await asyncio.sleep(1.0)
        app.send_cmd("GPIO32")
        await asyncio.sleep(0.5)

        lines = list(bridge.line_buffer)

        # Collect lines that seem related to GPIO response
        relevant = [l for l in lines if "GPIO" in l and l.startswith(">") is False]
        if not relevant:
            relevant = lines[-10:]  # show last 10 lines if nothing GPIO-specific

        report = "\n".join(relevant[:8])  # max 8 lines in notification
        self.notify(
            f"GPIO parancs nyers válasz ({len(relevant)} sor):\n{report}",
            severity="information",
            timeout=30,
        )

    async def _verify_relay_state(self) -> None:
        """Wait briefly then query Status 11 to confirm relay state changed."""
        await asyncio.sleep(0.6)
        app = self.app  # type: ignore[attr-defined]
        bridge = app.http_bridge if app.http_bridge.is_connected else app.serial_bridge
        if not bridge.is_connected:
            return
        try:
            bridge.clear_buffer()
            app.send_cmd("Status 11")
            await asyncio.sleep(0.5)
            lines = list(bridge.line_buffer)
            self._apply_status11(_parse_status11(lines))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI panel updates
    # ------------------------------------------------------------------

    def _update_device_panel(self) -> None:
        try:
            hostname = self._dev_hostname or self._dev_topic or "–"
            self.query_one("#board-dev-hostname").update(
                f"[dim]Hostname:[/dim]  [bold]{hostname}[/bold]"
            )
            topic = self._dev_topic or "–"
            self.query_one("#board-dev-topic").update(
                f"[dim]Topic:[/dim]     [cyan]{topic}[/cyan]"
            )
            fw = f"v{self._dev_firmware}" if self._dev_firmware else "–"
            self.query_one("#board-dev-firmware").update(
                f"[dim]Firmware:[/dim]  [green]{fw}[/green]"
            )
            hw = self._dev_hardware or "–"
            self.query_one("#board-dev-hardware").update(
                f"[dim]Chip:[/dim]      {hw}"
            )
            if self._dev_heap:
                color = "green" if self._dev_heap > 20 else "yellow" if self._dev_heap > 10 else "red"
                self.query_one("#board-dev-heap").update(
                    f"[dim]Szabad RAM:[/dim] [{color}]{self._dev_heap} kB[/{color}]"
                )
        except Exception:
            pass

    def _update_mqtt_panel(self) -> None:
        try:
            if self._mqtt_host:
                port = f":{self._mqtt_port}" if self._mqtt_port else ""
                self.query_one("#board-mqtt-broker").update(
                    f"[dim]Broker:[/dim]  [cyan]{self._mqtt_host}{port}[/cyan]"
                )
            else:
                self.query_one("#board-mqtt-broker").update("[dim]Broker: –[/dim]")
            if self._mqtt_client:
                self.query_one("#board-mqtt-client").update(
                    f"[dim]Kliens:[/dim]  {self._mqtt_client}"
                )
            if self._mqtt_count is not None and self._mqtt_count > 0:
                self.query_one("#board-mqtt-count").update(
                    f"[dim]Kapcsolódások:[/dim] {self._mqtt_count}"
                )
        except Exception:
            pass

    def _update_wifi_panel(self) -> None:
        try:
            connected = (
                bool(self._wifi_ip)
                and self._wifi_ip not in ("0.0.0.0", "")
            )
            if connected:
                self.query_one("#board-wifi-state").update("[green]● Csatlakozva[/green]")
            elif self._wifi_ssid:
                self.query_one("#board-wifi-state").update("[yellow]● Csatlakozás...[/yellow]")
            else:
                self.query_one("#board-wifi-state").update("[dim]● –[/dim]")
            self.query_one("#board-wifi-ssid").update(
                f"[dim]SSID:[/dim]  [bold]{self._wifi_ssid or '–'}[/bold]"
            )
            self.query_one("#board-wifi-ip").update(
                f"[dim]IP:[/dim]    [cyan]{self._wifi_ip or '–'}[/cyan]"
            )
            if self._wifi_rssi is not None:
                bars  = rssi_to_bars(self._wifi_rssi)
                qlbl  = rssi_label(self._wifi_rssi)
                color = ("green" if self._wifi_rssi > -70
                         else "yellow" if self._wifi_rssi > -80
                         else "red")
                self.query_one("#board-wifi-signal").update(
                    f"[dim]Jel:[/dim]   [{color}]{bars}[/{color}]"
                    f"  {self._wifi_rssi} dBm  ({qlbl})"
                )
            else:
                self.query_one("#board-wifi-signal").update("[dim]Jelerősség: –[/dim]")
        except Exception:
            pass

    def _update_sensor_panel(self) -> None:
        try:
            sensor_lbl: Label = self.query_one("#board-sensor-values")
            energy_lbl: Label = self.query_one("#board-energy-values")

            # Sensor readings
            parts: list[str] = []
            for name, data in self._sensor_data.items():
                if not isinstance(data, dict):
                    continue
                vals: list[str] = []
                if "Temperature" in data:
                    vals.append(f"[red]{data['Temperature']} °C[/red]")
                if "Humidity" in data:
                    vals.append(f"[cyan]{data['Humidity']} %rH[/cyan]")
                if "Pressure" in data:
                    vals.append(f"{data['Pressure']} hPa")
                if "DewPoint" in data:
                    vals.append(f"Harmatpont: {data['DewPoint']} °C")
                if vals:
                    parts.append(f"[bold]{name}:[/bold] " + "  ".join(vals))
            sensor_lbl.update("\n".join(parts) if parts else "[dim]Nincs szenzor adat[/dim]")

            # Energy / power monitoring
            e = self._energy_data
            if e:
                power   = e.get("Power",   e.get("ActivePower"))
                voltage = e.get("Voltage")
                current = e.get("Current")
                e_today = e.get("Today")
                e_total = e.get("Total")
                e_parts: list[str] = []
                if power   is not None: e_parts.append(f"[yellow]{power} W[/yellow]")
                if voltage is not None: e_parts.append(f"{voltage} V")
                if current is not None: e_parts.append(f"{current} A")
                if e_today is not None: e_parts.append(f"Ma: {e_today} kWh")
                if e_total is not None: e_parts.append(f"Össz: {e_total} kWh")
                energy_lbl.update("[bold]Energiafogyasztás:[/bold]  " + "  ".join(e_parts))
            else:
                energy_lbl.update("")
        except Exception:
            pass
