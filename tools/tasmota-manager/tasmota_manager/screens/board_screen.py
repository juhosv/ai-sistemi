"""Board Monitor tab – real-time visual pin state map + device info panel."""
from __future__ import annotations

import asyncio
import json
import re
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
    """StatusSNS → sensor readings dict + energy dict."""
    result: dict = {"sensors": {}, "energy": {}}
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
    return result


def _parse_status11(lines: list[str]) -> dict:
    """StatusSTS → power states, uptime, WiFi signal."""
    result: dict = {"power": {}, "uptime": "", "wifi_rssi": None}
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


def _parse_gpio_from_device(lines: list[str]) -> dict[int, str]:
    """
    Parse GPIO assignments from Tasmota serial/MQTT responses.

    Priority order:
    1. Status 13  → {"StatusGPIO":{"GPIO0":0,"GPIO4":160,"GPIO12":21,...}}
       This is the most reliable source (Tasmota 12+).
    2. Individual GPIO query  → {"GPIO4":160} (sent per-pin, not used currently)

    Returns {gpio_num: type_id} using the reverse code table.
    Only non-zero (assigned) GPIOs are included.
    """
    result: dict[int, str] = {}

    # --- Strategy 1: Status 13 → StatusGPIO ----------------------------
    for line in lines:
        if "StatusGPIO" not in line:
            continue
        data = _extract_json(line)
        if not data:
            continue
        gpio_map = data.get("StatusGPIO", {})
        if not isinstance(gpio_map, dict):
            continue
        for key, val in gpio_map.items():
            # Keys like "GPIO0", "GPIO4", ...
            m = re.match(r"GPIO(\d+)$", key)
            if not m:
                continue
            gpio_num = int(m.group(1))
            code = _to_code(val)
            if code and code != 0:
                type_id = _TASMOTA_CODE_TO_TYPE.get(code)
                if type_id and type_id != "none":
                    result[gpio_num] = type_id
        if result:
            return result   # got valid data from Status 13 – done

    # --- Strategy 2: individual {"GPIOx": code} lines ------------------
    # These come from querying `GPIO 4`, `GPIO 12`, etc.
    for line in lines:
        if '"GPIO' not in line:
            continue
        data = _extract_json(line)
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            m = re.match(r"GPIO(\d+)$", key)
            if not m:
                continue
            gpio_num = int(m.group(1))
            code = _to_code(val)
            if code and code != 0:
                type_id = _TASMOTA_CODE_TO_TYPE.get(code)
                if type_id and type_id != "none":
                    result[gpio_num] = type_id

    return result


def _to_code(val: object) -> Optional[int]:
    """Convert a Tasmota GPIO value (int or 'Relay1 (21)' string) to numeric code."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        m = re.search(r"\((\d+)\)", val)
        if m:
            return int(m.group(1))
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return None


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

    def set_layout(self, layout: BoardLayout) -> None:
        self._layout = layout
        self.refresh_diagram()

    def set_pin_state(self, gpio: int, state: Optional[bool]) -> None:
        self._pin_states[gpio] = state
        self.refresh_diagram()

    def set_gpio_functions(self, assignments: dict[int, str]) -> None:
        self._gpio_functions = assignments
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
                l_dot  = self._pin_dot(lp)
                l_name = f"{lp.label:<4}"
                l_func = self._pin_func_label(lp)
                st_lp  = self._pin_states.get(lp.gpio) if lp.gpio is not None else None
                l_state = "[green]■ ON [/green]" if st_lp is True else "[dim]□ OFF[/dim]" if st_lp is False else "     "
                left_part = f"{l_name} {l_dot} {l_func:<14} {l_state}"
            else:
                left_part = " " * 28

            if rp:
                r_dot  = self._pin_dot(rp)
                r_name = f"{rp.label:<4}"
                r_func = self._pin_func_label(rp)
                st_rp  = self._pin_states.get(rp.gpio) if rp.gpio is not None else None
                r_state = "[green]■ ON [/green]" if st_rp is True else "[dim]□ OFF[/dim]" if st_rp is False else "     "
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

        table: DataTable = self.query_one("#board-pin-datatable")
        table.add_columns("Pin", "GPIO", "Funkció", "Irány", "Állapot")
        self._rebuild_pin_table()
        self._rebuild_outputs_panel()

        self.run_worker(self._mqtt_state_listener(), exclusive=True,  name="board_mqtt")
        self.run_worker(self._auto_poll_serial(),    exclusive=True,  name="board_serial_poll")
        self.run_worker(self._chip_watcher(),        exclusive=False, name="board_chip_watcher")

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
            if msg.command == "STATE":
                self._apply_state(msg.payload_json)
            elif msg.command == "SENSOR":
                self._apply_sensor(msg.payload_json)

    # ------------------------------------------------------------------
    # Serial polling
    # ------------------------------------------------------------------

    async def _poll_device(self) -> None:
        """Send Status 1/2/5/10/11/13 via serial and parse responses."""
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if self._polling:
            return
        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat! (Serial tab → Csatlakozás)",
                        severity="warning", timeout=5)
            return
        self._polling = True
        btn: Button = self.query_one("#board-poll-btn")
        btn.disabled = True
        btn.label = "Lekérés…"
        try:
            serial_bridge.clear_buffer()
            # Reset device info so stale data doesn't remain from previous session
            self._gpio_assignments = {}

            for cmd, delay in [
                ("Status 1",  0.5),   # topic, hostname
                ("Status 2",  0.5),   # firmware, hardware
                ("Status 4",  0.5),   # memory / heap
                ("Status 5",  0.6),   # WiFi IP/SSID/RSSI
                ("Status 6",  0.5),   # MQTT broker info
                ("Status 10", 0.6),   # sensors + energy
                ("Status 11", 0.6),   # GPIO states, uptime
                ("Status 13", 0.8),   # GPIO assignments (Tasmota 12+)
            ]:
                serial_bridge.send(cmd)
                await asyncio.sleep(delay)
            await asyncio.sleep(0.5)   # extra settle time

            lines = list(serial_bridge.line_buffer)
            self._apply_status1(_parse_status1(lines))
            self._apply_status2(_parse_status2(lines))
            self._apply_status4(_parse_status4(lines))
            self._apply_status5(_parse_status5(lines))
            self._apply_status6(_parse_status6(lines))
            self._apply_status10(_parse_status10(lines))
            self._apply_status11(_parse_status11(lines))

            # GPIO assignments from device (Status 13)
            gpio_from_device = _parse_gpio_from_device(lines)
            if gpio_from_device:
                self.update_gpio_assignments(gpio_from_device, from_device=True)
                self.notify(
                    f"GPIO kiosztás az eszközről: {len(gpio_from_device)} pin",
                    severity="information", timeout=3,
                )
            else:
                # Status 13 returned nothing – show diagnostic info
                s13_lines = [l for l in lines if "StatusGPIO" in l or "Status" in l]
                hint = f"({len(s13_lines)} státusz sor az eszköztől)" if s13_lines else "(nincs státusz sor)"
                self.notify(
                    f"GPIO kiosztás nem érkezett az eszköztől {hint}\n"
                    "Ellenőrizd: Status 13 a Serial tabban",
                    severity="warning", timeout=8,
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

    # ------------------------------------------------------------------
    # Pin table rebuild
    # ------------------------------------------------------------------

    def _rebuild_pin_table(self) -> None:
        try:
            table: DataTable = self.query_one("#board-pin-datatable")
        except Exception:
            return
        table.clear()
        board = self._current_board
        instances = compute_gpio_instances(self._gpio_assignments)

        for pin in sorted(board.pins, key=lambda p: (p.side, p.row)):
            if pin.gpio is None:
                continue
            type_id  = self._gpio_assignments.get(pin.gpio)
            gt       = GPIO_TYPE_BY_ID.get(type_id or "none")
            func_lbl = gt.label if (gt and type_id and type_id != "none") else "—"
            direction = gt.direction if (gt and type_id and type_id != "none") else "–"

            state = self._pin_states.get(pin.gpio)
            d_alias   = board.gpio_to_dpin.get(pin.gpio, "")
            pin_label = f"{d_alias} / GPIO{pin.gpio}" if d_alias else f"GPIO{pin.gpio}"
            if pin.boot_sensitive:
                pin_label += " ⚠"

            if state is True:
                state_text = Text("■ ON",  style="bold green")
            elif state is False:
                state_text = Text("□ OFF", style="dim")
            else:
                state_text = Text("–",     style="dim")

            table.add_row(pin_label, f"GPIO{pin.gpio}", func_lbl, direction, state_text)

    # ------------------------------------------------------------------
    # Outputs panel – dynamic command buttons
    # ------------------------------------------------------------------

    def _rebuild_outputs_panel(self) -> None:
        """Rebuild the output control buttons from current GPIO assignments."""
        self._outputs_build_ver += 1
        ver = self._outputs_build_ver
        self.call_after_refresh(self._do_rebuild_outputs, ver)

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

        # Collect commandable outputs: (gpio, type_id, instance_num)
        outputs: list[tuple[int, str, int]] = []
        type_counters: dict[str, int] = {}
        for gpio in sorted(self._gpio_assignments):
            t = self._gpio_assignments[gpio]
            if t in _OUTPUT_CMD:
                type_counters[t] = type_counters.get(t, 0) + 1
                outputs.append((gpio, t, type_counters[t]))

        if not outputs:
            container.mount(Label("[dim]Nincs konfigurált kimenet[/dim]",
                                  classes="board-output-empty"))
            return

        for gpio, type_id, inst in outputs:
            gt = GPIO_TYPE_BY_ID.get(type_id)
            label_text = gt.label if gt else type_id
            # Short label
            short = (label_text
                     .replace("Relé / Kapcsoló kimenet", "Relé")
                     .replace("PWM fényerő szabályozás", "PWM")
                     .replace("Beépített státusz LED", "LED"))
            inst_lbl = instance_label(type_id, inst)
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
                name_label = Label(
                    f"{short} {inst}  [dim]({pin_name})[/dim]",
                    classes="board-output-name",
                )
                pwm_input = Input(
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
            serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
            if serial_bridge.is_connected:
                serial_bridge.send(f"{cmd} {value}")
                self.notify(f"Serial → {cmd} {value}", severity="information")
                sent = True
            else:
                self.notify(
                    "Nincs soros port kapcsolat! (Serial tab → Csatlakozás)",
                    severity="error", timeout=5,
                )
                return

        # For relay/LED commands: re-query Status 11 after short delay to confirm state
        if sent and cmd.startswith("POWER"):
            self.run_worker(self._verify_relay_state(), name="board_relay_verify")

    async def _verify_relay_state(self) -> None:
        """Wait briefly then query Status 11 to confirm relay state changed."""
        await asyncio.sleep(0.6)
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if not serial_bridge.is_connected:
            return
        try:
            serial_bridge.clear_buffer()
            serial_bridge.send("Status 11")
            await asyncio.sleep(0.5)
            lines = list(serial_bridge.line_buffer)
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
            if self._wifi_ssid or self._wifi_ip:
                self.query_one("#board-wifi-state").update("[green]● Csatlakozva[/green]")
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
