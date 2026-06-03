"""Board Monitor tab – real-time visual pin state map."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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

from tasmota_manager.board_layouts import (
    ALL_BOARDS,
    BOARD_BY_NAME,
    BoardLayout,
    PinDef,
    D1_MINI,
)
from tasmota_manager.config_builder import (
    GPIO_TYPE_BY_ID,
    assign_tasmota_codes,
    compute_gpio_instances,
)
from tasmota_manager.utils import rssi_to_bars, rssi_label


class BoardDiagram(Static):
    """Renders an ASCII board diagram with live pin state colors."""

    def __init__(self, layout: BoardLayout, **kwargs):
        super().__init__("", **kwargs)
        self._layout = layout
        self._pin_states: dict[int, Optional[bool]] = {}   # gpio → True/False/None
        self._gpio_functions: dict[int, str] = {}          # gpio → type_id

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
        # Shorten for display
        label = label.replace("Bemeneti érzékelő", "Bem. érz.")
        label = label.replace("Relé / Kapcsoló kimenet", "Relé kim.")
        label = label.replace("Nyomógomb (fizikai)", "Nyomógomb")
        label = label.replace("Impulzusszámláló", "Impulzussz.")
        label = label.replace("PWM fényerő szabályozás", "PWM")
        label = label.replace("Beépített státusz LED", "Beép. LED")
        label = label.replace("DHT22 / AM2301 – hőmérséklet + páratartalom", "DHT22")
        label = label.replace("DHT11 – hőmérséklet + páratartalom", "DHT11")
        label = label.replace("DS18B20 – hőmérséklet szenzor (1-Wire)", "DS18B20")
        label = label.replace("I2C busz – SCL (órajel)", "I2C SCL")
        label = label.replace("I2C busz – SDA (adat)", "I2C SDA")
        if len(label) > 14:
            label = label[:13] + "…"
        return label

    def _render_diagram(self) -> str:
        layout = self._layout
        w = layout.display_width

        left_pins = sorted(
            [p for p in layout.pins if p.side == "left"], key=lambda x: x.row
        )
        right_pins = sorted(
            [p for p in layout.pins if p.side == "right"], key=lambda x: x.row
        )
        rows = max(len(left_pins), len(right_pins))

        lines: list[str] = []
        lines.append(f"┌{'─' * (w - 2)}┐")
        lines.append(f"│{'   ' + layout.name:^{w - 2}}│")
        lines.append(f"│{'':^{w - 2}}│")

        for i in range(rows):
            lp = left_pins[i] if i < len(left_pins) else None
            rp = right_pins[i] if i < len(right_pins) else None

            if lp:
                l_dot = self._pin_dot(lp)
                l_name = f"{lp.label:<4}"
                l_func = self._pin_func_label(lp)
                state_lp = self._pin_states.get(lp.gpio) if lp.gpio else None
                if state_lp is True:
                    l_state = "[green]■ ON [/green]"
                elif state_lp is False:
                    l_state = "[dim]□ OFF[/dim]"
                else:
                    l_state = "     "
                left_part = f"{l_name} {l_dot} {l_func:<14} {l_state}"
            else:
                left_part = " " * 28

            if rp:
                r_dot = self._pin_dot(rp)
                r_name = f"{rp.label:<4}"
                r_func = self._pin_func_label(rp)
                state_rp = self._pin_states.get(rp.gpio) if rp.gpio else None
                if state_rp is True:
                    r_state = "[green]■ ON [/green]"
                elif state_rp is False:
                    r_state = "[dim]□ OFF[/dim]"
                else:
                    r_state = "     "
                right_part = f"{r_state} {r_func:<14} {r_dot} {r_name}"
            else:
                right_part = " " * 28

            lines.append(f"│ {left_part}  │  {right_part} │")

        lines.append(f"└{'─' * (w - 2)}┘")
        return "\n".join(lines)


class BoardTab(TabPane):
    """Visual board pin state monitor."""

    DEFAULT_CSS = ""
    _current_board: BoardLayout = D1_MINI
    _pin_states: dict[int, Optional[bool]] = {}
    _sensor_data: dict[str, object] = {}
    _wifi_rssi: Optional[int] = None
    _wifi_ip: str = ""
    _uptime: str = ""
    _gpio_assignments: dict[int, str] = {}

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
                yield Label("", id="board-uptime-label")
                yield Button("↺ Lekérés", id="board-poll-btn", variant="default")

            # --- Board diagram ------------------------------------------
            yield BoardDiagram(D1_MINI, id="board-diagram", markup=True)

            # --- Sensor values ------------------------------------------
            with Vertical(id="board-sensors"):
                yield Static("Szenzor értékek", classes="section-title")
                yield Label("–", id="board-sensor-label")
                yield Label("–", id="board-wifi-label")

            # --- Pin table ----------------------------------------------
            with Vertical(id="board-pin-table"):
                yield Static("Pin állapot táblázat", classes="section-title")
                yield DataTable(id="board-pin-datatable", show_header=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#board-pin-datatable")
        table.add_columns("Pin", "GPIO", "Funkció", "Irány", "Állapot")
        self._rebuild_pin_table()
        self.run_worker(self._mqtt_state_listener(), exclusive=True, name="board_mqtt")
        self.run_worker(self._auto_poll_serial(), exclusive=True, name="board_serial_poll")

    # ------------------------------------------------------------------
    # Select handler (board type change)
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "board-type-select" and event.value is not Select.BLANK:
            board = BOARD_BY_NAME.get(str(event.value), D1_MINI)
            self._current_board = board
            diagram: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
            diagram.set_layout(board)
            diagram.set_gpio_functions(self._gpio_assignments)
            self._rebuild_pin_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "board-poll-btn":
            self.run_worker(self._poll_serial_once(), name="board_manual_poll")

    # ------------------------------------------------------------------
    # MQTT state listener
    # ------------------------------------------------------------------

    async def _mqtt_state_listener(self) -> None:
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        while True:
            try:
                msg = await asyncio.wait_for(mqtt_mgr.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.5)
                continue

            # Re-put the message so MQTT monitor tab can also consume it
            mqtt_mgr.queue.put_nowait(msg)

            if msg.command == "STATE":
                self._parse_state(msg.payload_json)
            elif msg.command == "SENSOR":
                self._parse_sensor(msg.payload_json)

    # ------------------------------------------------------------------
    # Serial poll for board state
    # ------------------------------------------------------------------

    async def _auto_poll_serial(self) -> None:
        while True:
            await asyncio.sleep(5)
            rs: RadioSet = self.query_one("#board-source-radio")
            if rs.pressed_index == 1:  # Serial mode selected
                await self._poll_serial_once()

    async def _poll_serial_once(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if serial_bridge.is_connected:
            try:
                serial_bridge.send("Status 11")
                await asyncio.sleep(0.5)
                serial_bridge.send("Status 10")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Parse Tasmota state payloads
    # ------------------------------------------------------------------

    def _parse_state(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        # Relay/POWER states
        for key, val in payload.items():
            m = re.match(r"POWER(\d*)", key)
            if m:
                relay_idx = int(m.group(1) or "1")
                # Find GPIO assigned to relay{relay_idx}
                gpio = self._find_gpio_for_instance("relay", relay_idx)
                if gpio is not None:
                    self._set_pin_state(gpio, val == "ON")

        # WiFi info
        wifi = payload.get("Wifi", {})
        if isinstance(wifi, dict):
            self._wifi_rssi = wifi.get("Signal") or wifi.get("RSSI")
            self._wifi_ip = ""
        self._uptime = str(payload.get("Uptime", ""))
        self._update_wifi_label()
        uptime_lbl: Label = self.query_one("#board-uptime-label")
        uptime_lbl.update(f"Uptime: {self._uptime}")

    def _parse_sensor(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        # Switch states (edge-triggered)
        for key, val in payload.items():
            m = re.match(r"Switch(\d+)", key)
            if m:
                switch_idx = int(m.group(1))
                gpio = self._find_gpio_for_instance("switch", switch_idx)
                if gpio is not None:
                    self._set_pin_state(gpio, val == "ON")

        # Sensor readings
        sensor_keys = ["AM2301", "DHT11", "DS18B20", "BME280", "SHT3X"]
        sensor_data: dict[str, object] = {}
        for k in sensor_keys:
            if k in payload:
                sensor_data[k] = payload[k]
        if sensor_data:
            self._sensor_data = sensor_data
            self._update_sensor_label()

    # ------------------------------------------------------------------
    # Pin state management
    # ------------------------------------------------------------------

    def _set_pin_state(self, gpio: int, state: Optional[bool]) -> None:
        self._pin_states[gpio] = state
        diagram: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
        diagram.set_pin_state(gpio, state)
        self._rebuild_pin_table()

    def _find_gpio_for_instance(self, type_id: str, instance: int) -> Optional[int]:
        type_counter: dict[str, int] = {}
        for gpio_num in sorted(self._gpio_assignments.keys()):
            t = self._gpio_assignments[gpio_num]
            type_counter[t] = type_counter.get(t, 0) + 1
            if t == type_id and type_counter[t] == instance:
                return gpio_num
        return None

    # ------------------------------------------------------------------
    # GPIO assignments sync (called from app when config changes)
    # ------------------------------------------------------------------

    def update_gpio_assignments(self, assignments: dict[int, str]) -> None:
        self._gpio_assignments = assignments
        diagram: BoardDiagram = self.query_one("#board-diagram", BoardDiagram)
        diagram.set_gpio_functions(assignments)
        self._rebuild_pin_table()

    # ------------------------------------------------------------------
    # Pin table rebuild
    # ------------------------------------------------------------------

    def _rebuild_pin_table(self) -> None:
        table: DataTable = self.query_one("#board-pin-datatable")
        table.clear()

        board = self._current_board
        instances = compute_gpio_instances(self._gpio_assignments)

        for pin in sorted(board.pins, key=lambda p: (p.side, p.row)):
            if pin.gpio is None:
                continue

            type_id = self._gpio_assignments.get(pin.gpio)
            gt = GPIO_TYPE_BY_ID.get(type_id or "none")
            func_label = gt.label if (gt and type_id and type_id != "none") else "—"
            direction = gt.direction if (gt and type_id and type_id != "none") else "–"

            state = self._pin_states.get(pin.gpio)
            d_alias = board.gpio_to_dpin.get(pin.gpio, "")
            pin_label = f"{d_alias} / GPIO{pin.gpio}" if d_alias else f"GPIO{pin.gpio}"

            if pin.boot_sensitive:
                pin_label += " ⚠"
                func_label = func_label or "[Boot érzékeny]"

            if state is True:
                state_text = Text("■ ON", style="bold green")
            elif state is False:
                state_text = Text("□ OFF", style="dim")
            else:
                state_text = Text("–", style="dim")

            table.add_row(pin_label, f"GPIO{pin.gpio}", func_label, direction, state_text)

    # ------------------------------------------------------------------
    # Label updates
    # ------------------------------------------------------------------

    def _update_sensor_label(self) -> None:
        lbl: Label = self.query_one("#board-sensor-label")
        parts: list[str] = []
        for sensor_name, data in self._sensor_data.items():
            if isinstance(data, dict):
                vals = []
                if "Temperature" in data:
                    vals.append(f"Hőmérséklet: {data['Temperature']} °C")
                if "Humidity" in data:
                    vals.append(f"Páratartalom: {data['Humidity']} %")
                if "Pressure" in data:
                    vals.append(f"Nyomás: {data['Pressure']} hPa")
                parts.append(f"{sensor_name}: " + "   ".join(vals))
        lbl.update("   ".join(parts) if parts else "–")

    def _update_wifi_label(self) -> None:
        lbl: Label = self.query_one("#board-wifi-label")
        if self._wifi_rssi is not None:
            bars = rssi_to_bars(self._wifi_rssi)
            quality = rssi_label(self._wifi_rssi)
            ip_part = f"   IP: {self._wifi_ip}" if self._wifi_ip else ""
            lbl.update(
                f"WiFi RSSI: {self._wifi_rssi} dBm  "
                f"[{'green' if self._wifi_rssi > -70 else 'yellow'}]{bars}[/] {quality}{ip_part}"
            )
        else:
            lbl.update("WiFi: –")
