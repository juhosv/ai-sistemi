"""Configuration tab – WiFi, MQTT, GPIO setup with profile management."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    Select,
    Static,
    TabPane,
)

# -----------------------------------------------------------------------
# Tasmota Status response parsers
# -----------------------------------------------------------------------

def _extract_json_block(text: str) -> Optional[dict]:
    """Find and parse the first JSON object in *text*."""
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


def parse_status1(lines: list[str]) -> dict:
    """Parse Status 1 (StatusPRM / Status) – topic, module, full_topic."""
    result: dict = {}
    for line in lines:
        if "StatusPRM" not in line and '"Status"' not in line:
            continue
        data = _extract_json_block(line)
        if not data:
            continue
        block = data.get("StatusPRM") or data.get("Status") or {}
        if "Topic" in block:
            result["topic"] = block["Topic"]
        if "FullTopic" in block:
            result["full_topic"] = block["FullTopic"]
        if "Module" in block:
            result["module_type"] = block["Module"]
        if "DeviceName" in block:
            result["device_name"] = block["DeviceName"]
    return result


def parse_status5(lines: list[str]) -> dict:
    """Parse Status 5 (StatusNET) – WiFi SSID, IP (no password)."""
    result: dict = {}
    for line in lines:
        if "StatusNET" not in line:
            continue
        data = _extract_json_block(line)
        if not data:
            continue
        net = data.get("StatusNET", {})
        if "SSId" in net:
            result["ssid1"] = net["SSId"]
        if "IPAddress" in net:
            result["ip"] = net["IPAddress"]
        if "RSSI" in net:
            result["rssi"] = net["RSSI"]
    return result


def parse_status6(lines: list[str]) -> dict:
    """Parse Status 6 (StatusMQT) – host, port, user, topic (no password)."""
    result: dict = {}
    for line in lines:
        if "StatusMQT" not in line:
            continue
        data = _extract_json_block(line)
        if not data:
            continue
        mqt = data.get("StatusMQT", {})
        if "MqttHost" in mqt:
            result["mqtt_host"] = mqt["MqttHost"]
        if "MqttPort" in mqt:
            result["mqtt_port"] = str(mqt["MqttPort"])
        if "MqttUser" in mqt:
            result["mqtt_user"] = mqt["MqttUser"]
        # MqttPassword is never returned by Tasmota
    return result


def parse_ssids(lines: list[str]) -> dict:
    """
    Parse Ssid1 / Ssid2 console command responses.

    Tasmota returns individual JSON lines when you send 'Ssid1' / 'Ssid2':
        {"Ssid1":"HomeNetwork"}
        {"Ssid2":"BackupNet"}

    Also handles the case where Status 5 is the only WiFi source (active SSID).
    """
    result: dict = {}
    for line in lines:
        data = _extract_json_block(line)
        if not data:
            continue
        if "Ssid1" in data and data["Ssid1"]:
            result["ssid1"] = data["Ssid1"]
        if "Ssid2" in data:
            result["ssid2"] = data["Ssid2"]  # may be empty string = not set
    return result


def parse_status2(lines: list[str]) -> Optional[str]:
    """Parse Status 2 (StatusFWR) – return chip family string or None."""
    for line in lines:
        if "StatusFWR" not in line:
            continue
        data = _extract_json_block(line)
        if not data:
            continue
        hw = data.get("StatusFWR", {}).get("Hardware", "")
        if "ESP32-S3" in hw:
            return "ESP32-S3"
        if "ESP32-C3" in hw:
            return "ESP32-C3"
        if "ESP32" in hw:
            return "ESP32"
        if "ESP8266" in hw or "8266" in hw:
            return "ESP8266"
    # Fallback: scan boot lines for ESP-IDF marker (ESP32 only)
    for line in lines:
        if "ESP-IDF" in line:
            return "ESP32"
    return None

def parse_wifi_scan(lines: list[str]) -> list[dict]:
    """
    Parse Tasmota WiFiScan command responses.

    Tasmota WifiScan protocol (two-step):
      1. Send "WifiScan 1"  → starts async scan, returns {"WifiScan":"Scanning"}
      2. Wait ~3 s, then "WifiScan" → returns cached results

    Combined result format (single JSON, all networks):
        {"WiFiScan":{"NET1":{"SSId":"HomeNet","BSSId":"AA:BB:...",
                             "Channel":"6","Signal":"-31","RSSI":"100",
                             "Encryption":"WPA2/PSK"},
                     "NET2":{...}}}

    The same networks also appear individually via MQTT (one per RESULT line):
        MQT: stat/.../RESULT = {"WiFiScan":{"NET1":{...}}}
        MQT: stat/.../RESULT = {"WiFiScan":{"NET2":{...}}}

    Note: key is "WiFiScan" (capital F) in responses; command is "WifiScan".
    Both spellings are handled. Signal/RSSI values come as strings.

    Returns list of dicts: [{"ssid":..., "rssi":...(dBm), "enc":...}, ...]
    sorted by signal strength (strongest first), duplicates removed.
    """
    seen: dict[str, dict] = {}

    for line in lines:
        if "WiFiScan" not in line and "WifiScan" not in line:
            continue
        data = _extract_json_block(line)
        if not data:
            continue

        # Handle both capitalisation variants
        scan_val = data.get("WiFiScan") or data.get("WifiScan")
        if not isinstance(scan_val, dict):
            continue  # skip "Scanning", "Not Started", "Busy" strings

        # scan_val may be the whole dict of networks OR a single-network dict
        # Detect: if keys are NET1/NET2/... it's the combined result
        if any(k.startswith("NET") for k in scan_val):
            networks_iter = scan_val.values()
        else:
            # Single network dict (e.g. individual MQTT RESULT line)
            networks_iter = [scan_val]

        for net in networks_iter:
            if not isinstance(net, dict):
                continue
            ssid = net.get("SSId", "")
            if not ssid:
                continue
            # Signal = dBm (string, e.g. "-31"), RSSI = percentage string
            try:
                rssi = int(net.get("Signal", "0"))
            except ValueError:
                # Fallback: convert RSSI percentage to dBm
                try:
                    rssi = int(net.get("RSSI", "0")) // 2 - 100
                except ValueError:
                    rssi = -100
            enc = net.get("Encryption", "?")
            # Keep strongest signal for duplicate SSIDs
            if ssid not in seen or rssi > seen[ssid]["rssi"]:
                seen[ssid] = {"ssid": ssid, "rssi": rssi, "enc": enc}

    return sorted(seen.values(), key=lambda x: x["rssi"], reverse=True)


from tasmota_manager.board_layouts import (
    BOARD_BY_NAME,
    BoardLayout,
    D1_MINI,
    MODULE_SELECT_OPTIONS,
    PinDef,
)
from tasmota_manager.config_builder import (
    GPIO_FUNCTION_TYPES,
    GPIO_TYPE_BY_ID,
    DeviceConfig,
    GpioType,
    MqttConfig,
    WifiConfig,
    assign_tasmota_codes,
    compute_gpio_instances,
    gpio_select_options,
    list_profiles,
    load_profile,
    save_profile,
)


_GPIO_SELECT_OPTIONS = gpio_select_options()
_GPIO_SELECT_OPTIONS_CLEAN = [
    (lbl, val) for lbl, val in _GPIO_SELECT_OPTIONS
    if not val.startswith("__sep_")
]


class InteractiveBoardDiagram(Widget):
    """Interactive board pinout diagram for the Config tab.

    GPIO pins render as clickable Buttons (green = assigned, default = unassigned,
    yellow = currently selected). Power / UART / ADC pins are non-interactive Labels.
    Button.Pressed events bubble up naturally to ConfigTab for handling.
    """

    DEFAULT_CSS = ""

    def __init__(
        self,
        layout: BoardLayout,
        assignments: dict[int, str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._layout = layout
        self._assignments = dict(assignments)

    def compose(self) -> ComposeResult:
        left_pins = sorted(
            [p for p in self._layout.pins if p.side == "left"],
            key=lambda p: p.row,
        )
        right_pins = sorted(
            [p for p in self._layout.pins if p.side == "right"],
            key=lambda p: p.row,
        )
        with Horizontal(classes="ibd-columns"):
            with Vertical(classes="ibd-col ibd-left"):
                for pin in left_pins:
                    yield self._pin_widget(pin)
            with Vertical(classes="ibd-chip-body"):
                yield Static(f"\n{self._layout.chip}\n", classes="ibd-chip-label")
            with Vertical(classes="ibd-col ibd-right"):
                for pin in right_pins:
                    yield self._pin_widget(pin)

    def _pin_widget(self, pin: PinDef) -> Button | Static:
        """Button for a configurable GPIO; Label for power/UART/ADC pins."""
        gpio = pin.gpio
        configurable = (
            gpio is not None
            and not pin.is_power
            and not pin.is_uart
            and not pin.adc_only
        )
        if configurable:
            assigned = self._assignments.get(gpio)
            has_assign = bool(assigned and assigned != "none")
            boot = "⚠" if pin.boot_sensitive else ""
            if has_assign:
                label = f"{boot}{pin.label} ✓"
                variant = "success"
            else:
                label = f"{boot}{pin.label}"
                variant = "default"
            return Button(
                label,
                id=f"cfgpin_{gpio}",
                classes="ibd-pin-gpio" + (" ibd-pin-boot" if pin.boot_sensitive else ""),
                variant=variant,
            )
        else:
            if pin.is_power:
                classes = "ibd-pin-power"
            elif pin.is_uart:
                classes = "ibd-pin-uart"
            else:
                classes = "ibd-pin-adc"
            return Static(f" {pin.label} ", classes=classes)

    def update_pin(self, gpio_num: int, type_id: str) -> None:
        """Refresh a single pin button after an assignment change."""
        try:
            btn: Button = self.query_one(f"#cfgpin_{gpio_num}")
            pin = self._layout.pin_by_gpio(gpio_num)
            pin_label = pin.label if pin else f"G{gpio_num}"
            boot = "⚠" if (pin and pin.boot_sensitive) else ""
            if type_id and type_id != "none":
                btn.label = f"{boot}{pin_label} ✓"
                btn.variant = "success"
            else:
                btn.label = f"{boot}{pin_label}"
                btn.variant = "default"
            self._assignments[gpio_num] = type_id
        except Exception:
            pass


class ConfigTab(TabPane):
    """Full device configuration editor."""

    DEFAULT_CSS = ""
    _gpio_assignments: dict[int, str]   # gpio_num → type_id
    _selected_gpio: Optional[int]       # currently selected pin in the diagram
    _diagram_build_version: int         # version counter for deduplicating rebuilds

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="config-tab"):

            # --- Profile row --------------------------------------------
            with Horizontal(id="config-profile-row"):
                yield Label("Profil:", classes="label")
                yield Select(
                    options=self._profile_options(),
                    id="config-profile-select",
                    allow_blank=True,
                )
                yield Button("📂 Betöltés", id="cfg-load-btn", variant="default")
                yield Button("💾 Mentés", id="cfg-save-btn", variant="primary")
                yield Input(placeholder="Profil neve", id="cfg-profile-name-input", value="uj_profil")

            # --- Device fetch row ---------------------------------------
            with Horizontal(id="config-fetch-row"):
                yield Button(
                    "📥 Letöltés eszközről  (Status 1 / 5 / 6 / 2)",
                    id="cfg-fetch-btn",
                    variant="warning",
                )
                yield Label(
                    "  Soros portkapcsolat szükséges (Serial tab → Csatlakozás)",
                    id="cfg-fetch-hint",
                    classes="hint",
                )
                yield Label("", id="cfg-fetch-status")

            # --- Top panels: WiFi + MQTT --------------------------------
            with Horizontal(id="config-top-panels"):
                with Vertical(id="wifi-panel"):
                    yield Static("WiFi", classes="section-title")

                    # --- Scan row (always visible) ---
                    with Horizontal(id="wifi-scan-row"):
                        yield Button("📡 Szkennelés", id="wifi-scan-btn", variant="default")
                        yield Label("", id="wifi-scan-status")

                    # --- Scan results (hidden until scan runs) ---
                    with Vertical(id="wifi-scan-results"):
                        yield Select(
                            options=[],
                            id="wifi-scan-select",
                            allow_blank=True,
                            prompt="– válassz hálózatot –",
                        )
                        with Horizontal(id="wifi-pick-row"):
                            yield Button("→ SSID 1-be", id="wifi-pick-ssid1", variant="success")
                            yield Button("→ SSID 2-be", id="wifi-pick-ssid2", variant="default")

                    # --- Manual input rows ---
                    with Horizontal(classes="row"):
                        yield Label("SSID 1:", classes="label")
                        yield Input(placeholder="pl. HomeNetwork", id="cfg-ssid1")
                    with Horizontal(classes="row"):
                        yield Label("Jelszó 1:", classes="label")
                        yield Input(placeholder="••••••••", password=True, id="cfg-pass1")
                    with Horizontal(classes="row"):
                        yield Label("SSID 2:", classes="label")
                        yield Input(placeholder="Tartalék (opcionális)", id="cfg-ssid2")
                    with Horizontal(classes="row"):
                        yield Label("Jelszó 2:", classes="label")
                        yield Input(placeholder="••••••••", password=True, id="cfg-pass2")

                with Vertical(id="mqtt-panel"):
                    yield Static("MQTT", classes="section-title")
                    with Horizontal(classes="row"):
                        yield Label("Host:", classes="label")
                        yield Input(value="broker.emqx.io", id="cfg-mqtt-host")
                    with Horizontal(classes="row"):
                        yield Label("Port:", classes="label")
                        yield Input(value="1883", id="cfg-mqtt-port")
                    with Horizontal(classes="row"):
                        yield Label("User:", classes="label")
                        yield Input(placeholder="(üresen hagyható)", id="cfg-mqtt-user")
                    with Horizontal(classes="row"):
                        yield Label("Jelszó:", classes="label")
                        yield Input(placeholder="(üresen hagyható)", password=True, id="cfg-mqtt-pass")
                    with Horizontal(classes="row"):
                        yield Label("Topic:", classes="label")
                        yield Input(placeholder="pl. A1B2C3", id="cfg-mqtt-topic")
                    with Horizontal(classes="row"):
                        yield Label("FullTopic:", classes="label")
                        yield Input(value="%prefix%/%topic%/", id="cfg-mqtt-fulltopic")

            # --- General settings ---------------------------------------
            with Horizontal(id="general-panel"):
                with Vertical(id="general-left"):
                    yield Static("Általános", classes="section-title")
                    with Horizontal(classes="row"):
                        yield Label("Device Topic:", classes="label")
                        yield Input(placeholder="pl. A1B2C3", id="cfg-topic")
                    with Horizontal(classes="row"):
                        yield Label("TelePeriod:", classes="label")
                        yield Input(value="300", id="cfg-teleperiod")
                    with Horizontal(classes="row"):
                        yield Label("Modul / Board:", classes="label")
                        yield Select(
                            options=MODULE_SELECT_OPTIONS,
                            value=D1_MINI.name,
                            id="cfg-module",
                            allow_blank=False,
                        )

            # --- GPIO assignment ----------------------------------------
            with Horizontal(id="gpio-panel"):
                # Left: Interactive board diagram
                with Vertical(id="gpio-board-col"):
                    yield Static("GPIO kiosztás", classes="section-title")
                    yield Label(
                        "Kattints egy [bold]GPIO[/bold] pinre a funkció beállításához",
                        id="gpio-board-hint",
                        classes="hint",
                    )
                    yield Vertical(id="gpio-diagram-container")
                # Right: Pin configuration flyout
                with Vertical(id="gpio-config-col"):
                    yield Static("Pin beállítás", classes="section-title")
                    yield Label(
                        "← Kattints egy GPIO pinre",
                        id="gpio-config-placeholder",
                        classes="hint",
                    )
                    with Vertical(id="gpio-pin-form", classes="hidden"):
                        yield Label("", id="gpio-pin-header", classes="gpio-pin-header")
                        yield Label("", id="gpio-pin-boot-warn")
                        yield Label("Funkció:", classes="label")
                        yield Select(
                            options=_GPIO_SELECT_OPTIONS_CLEAN,
                            id="gpio-func-select",
                            allow_blank=False,
                        )
                        yield Label("", id="gpio-func-hint", classes="gpio-hint")
                        yield Label("", id="gpio-func-mqtt", classes="gpio-mqtt-hint")
                        with Horizontal(id="gpio-config-btns"):
                            yield Button("✓ Beállítás", id="gpio-set-btn", variant="success")
                            yield Button("✗ Törlés", id="gpio-clear-btn", variant="warning")

            # --- Preview table ------------------------------------------
            with Vertical(id="config-preview"):
                yield Static("Tasmota parancsok előnézete", classes="section-title")
                yield DataTable(id="config-preview-table", show_header=True)

            # --- Send buttons -------------------------------------------
            with Horizontal(id="config-send-row"):
                yield Button("📡 Küldés soros porton", id="cfg-send-serial-btn", variant="primary")
                yield Button("📡 Küldés MQTT-n", id="cfg-send-mqtt-btn", variant="success")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._gpio_assignments = {}
        self._selected_gpio = None
        self._diagram_build_version = 0
        table: DataTable = self.query_one("#config-preview-table")
        table.add_columns("Parancs", "Érték")
        self._refresh_profiles()
        self._rebuild_board_diagram()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "cfg-load-btn":
            self._load_profile()
        elif bid == "cfg-save-btn":
            self._save_profile()
        elif bid == "cfg-fetch-btn":
            self.run_worker(self._fetch_config_from_device(), name="cfg_fetch")
        elif bid == "wifi-scan-btn":
            self.run_worker(self._do_wifi_scan(), name="wifi_scan")
        elif bid in ("wifi-pick-ssid1", "wifi-pick-ssid2"):
            self._pick_wifi_to_input(bid)
        elif bid.startswith("cfgpin_"):
            gpio_num = int(bid.split("_", 1)[1])
            self._show_pin_config(gpio_num)
        elif bid == "gpio-set-btn":
            self._set_pin()
        elif bid == "gpio-clear-btn":
            self._clear_pin()
        elif bid == "cfg-send-serial-btn":
            self._send_via_serial()
        elif bid == "cfg-send-mqtt-btn":
            self._send_via_mqtt()

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.select.id or ""
        if sid == "cfg-module":
            self._rebuild_board_diagram()
            self._update_preview()
        elif sid == "gpio-func-select":
            self._update_func_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_preview()

    # ------------------------------------------------------------------
    # GPIO management – interactive board diagram
    # ------------------------------------------------------------------

    def _get_gpio_assignments(self) -> dict[int, str]:
        """Return current GPIO assignments, excluding unset ('none') pins."""
        return {k: v for k, v in self._gpio_assignments.items() if v and v != "none"}

    def _get_current_board(self) -> Optional[BoardLayout]:
        """Return the BoardLayout matching the currently selected module."""
        try:
            sel: Select = self.query_one("#cfg-module")
            if sel.value is not Select.BLANK:
                return BOARD_BY_NAME.get(str(sel.value))
        except Exception:
            pass
        return None

    def _rebuild_board_diagram(self) -> None:
        """Re-mount the InteractiveBoardDiagram for the selected board.

        Uses a version counter so that if this is called multiple times in the
        same frame (e.g. once from on_mount and once from on_select_changed for
        the initial Select value), only the *last* scheduled build actually runs.
        The board is re-queried inside _do_build so we always use the value
        that is current at render time, not at schedule time.
        """
        self._diagram_build_version += 1
        version = self._diagram_build_version

        def _do_build() -> None:
            # Bail out if a newer build has been scheduled since we were queued.
            if self._diagram_build_version != version:
                return
            board = self._get_current_board()
            if not board:
                return
            try:
                container = self.query_one("#gpio-diagram-container")
            except Exception:
                return
            container.remove_children()
            # No id= to avoid duplicate-ID errors if two builds race.
            diag = InteractiveBoardDiagram(board, self._gpio_assignments)
            container.mount(diag)
            # Hide config panel if selected pin doesn't exist on this board.
            if self._selected_gpio is not None and not board.pin_by_gpio(self._selected_gpio):
                self._selected_gpio = None
                try:
                    self.query_one("#gpio-pin-form").add_class("hidden")
                    self.query_one("#gpio-config-placeholder").remove_class("hidden")
                except Exception:
                    pass
            self._update_preview()

        self.call_after_refresh(_do_build)

    def _show_pin_config(self, gpio_num: int) -> None:
        """Highlight the clicked pin and populate the right-side config panel."""
        # Deselect previous pin
        if self._selected_gpio is not None and self._selected_gpio != gpio_num:
            self._refresh_pin_button(self._selected_gpio)

        self._selected_gpio = gpio_num

        # Highlight selected pin
        try:
            btn: Button = self.query_one(f"#cfgpin_{gpio_num}")
            btn.variant = "warning"
        except Exception:
            pass

        # Gather pin metadata
        board = self._get_current_board()
        pin = board.pin_by_gpio(gpio_num) if board else None
        d_alias = (board.gpio_to_dpin.get(gpio_num, "") if board else "")

        parts = [f"GPIO {gpio_num}"]
        if d_alias:
            parts.append(d_alias)
        if pin:
            parts.append(f"({pin.label})")
        self.query_one("#gpio-pin-header").update(
            "[bold]" + " / ".join(parts) + "[/bold]"
        )

        boot_warn: Label = self.query_one("#gpio-pin-boot-warn")
        if pin and pin.boot_sensitive:
            boot_warn.update(
                "[yellow]⚠  Boot-sensitive – befolyásolhatja az indítást[/yellow]"
            )
        else:
            boot_warn.update("")

        # Set current function in the select
        func_sel: Select = self.query_one("#gpio-func-select")
        func_sel.value = self._gpio_assignments.get(gpio_num, "none")

        # Show the form
        self.query_one("#gpio-config-placeholder").add_class("hidden")
        self.query_one("#gpio-pin-form").remove_class("hidden")

        self._update_func_preview()

    def _refresh_pin_button(self, gpio_num: int) -> None:
        """Reset a pin button to its normal (non-selected) appearance."""
        try:
            btn: Button = self.query_one(f"#cfgpin_{gpio_num}")
            assigned = self._gpio_assignments.get(gpio_num)
            if assigned and assigned != "none":
                btn.variant = "success"
            else:
                btn.variant = "default"
        except Exception:
            pass

    def _set_pin(self) -> None:
        """Save the selected function for the currently highlighted pin."""
        if self._selected_gpio is None:
            return
        func_sel: Select = self.query_one("#gpio-func-select")
        if func_sel.value is Select.BLANK:
            return
        type_id = str(func_sel.value)
        self._gpio_assignments[self._selected_gpio] = type_id
        try:
            diag: InteractiveBoardDiagram = self.query_one(InteractiveBoardDiagram)
            diag.update_pin(self._selected_gpio, type_id)
        except Exception:
            pass
        # Mark button as selected (warning) again after update_pin resets it
        try:
            btn: Button = self.query_one(f"#cfgpin_{self._selected_gpio}")
            btn.variant = "warning"
        except Exception:
            pass
        self._update_preview()
        self._update_func_preview()
        gt = GPIO_TYPE_BY_ID.get(type_id)
        label = gt.label if gt else type_id
        self.notify(f"GPIO {self._selected_gpio} → {label}", severity="information")

    def _clear_pin(self) -> None:
        """Remove the assignment for the currently highlighted pin."""
        if self._selected_gpio is None:
            return
        self._gpio_assignments.pop(self._selected_gpio, None)
        try:
            diag: InteractiveBoardDiagram = self.query_one(InteractiveBoardDiagram)
            diag.update_pin(self._selected_gpio, "none")
        except Exception:
            pass
        # Keep pin highlighted as selected
        try:
            btn: Button = self.query_one(f"#cfgpin_{self._selected_gpio}")
            btn.variant = "warning"
        except Exception:
            pass
        func_sel: Select = self.query_one("#gpio-func-select")
        func_sel.value = "none"
        self._update_preview()
        self._update_func_preview()
        self.notify(f"GPIO {self._selected_gpio} törölve", severity="information")

    def _update_func_preview(self) -> None:
        """Update the hint / MQTT label in the pin config panel."""
        if self._selected_gpio is None:
            return
        try:
            func_sel: Select = self.query_one("#gpio-func-select")
            type_id = str(func_sel.value) if func_sel.value is not Select.BLANK else "none"
            hint_lbl: Label = self.query_one("#gpio-func-hint")
            mqtt_lbl: Label = self.query_one("#gpio-func-mqtt")
            if type_id == "none":
                hint_lbl.update("")
                mqtt_lbl.update("")
                return
            gt = GPIO_TYPE_BY_ID.get(type_id)
            if not gt:
                return
            hint_lbl.update(f"[dim]{gt.description}[/dim]" if gt.description else "")
            if gt.mqtt_example:
                preview = dict(self._gpio_assignments)
                preview[self._selected_gpio] = type_id
                instances = compute_gpio_instances(preview)
                n = instances.get(self._selected_gpio, "?")
                num_part = "".join(c for c in n if c.isdigit()) or "1"
                example = gt.mqtt_example.replace("{n}", num_part)
                mqtt_lbl.update(
                    f"[cyan]→ Tasmota: {n}[/cyan]   [dim]MQTT: {example}[/dim]"
                )
            else:
                mqtt_lbl.update("")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Preview table
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        cfg = self._build_config()
        table: DataTable = self.query_one("#config-preview-table")
        table.clear()
        for cmd, val in cfg.to_tasmota_commands():
            display_val = "****" if cmd in ("Password1", "Password2", "MqttPassword") and val else val
            table.add_row(cmd, display_val)

    # ------------------------------------------------------------------
    # Build config from form
    # ------------------------------------------------------------------

    def _build_config(self) -> DeviceConfig:
        def _val(sel_id: str) -> str:
            try:
                inp: Input = self.query_one(sel_id)
                return inp.value.strip()
            except Exception:
                return ""

        assignments = self._get_gpio_assignments()

        board_name = D1_MINI.name
        try:
            mod_sel: Select = self.query_one("#cfg-module")
            if mod_sel.value is not Select.BLANK:
                board_name = str(mod_sel.value)
        except Exception:
            pass

        return DeviceConfig(
            device_name=_val("#cfg-topic"),
            topic=_val("#cfg-mqtt-topic") or _val("#cfg-topic"),
            wifi=WifiConfig(
                ssid1=_val("#cfg-ssid1"),
                password1=_val("#cfg-pass1"),
                ssid2=_val("#cfg-ssid2"),
                password2=_val("#cfg-pass2"),
            ),
            mqtt=MqttConfig(
                host=_val("#cfg-mqtt-host"),
                port=int(_val("#cfg-mqtt-port") or "1883"),
                user=_val("#cfg-mqtt-user"),
                password=_val("#cfg-mqtt-pass"),
                topic=_val("#cfg-mqtt-topic"),
                full_topic=_val("#cfg-mqtt-fulltopic") or "%prefix%/%topic%/",
            ),
            tele_period=int(_val("#cfg-teleperiod") or "300"),
            module_type=board_name,
            gpio={str(k): v for k, v in assignments.items()},
        )

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def _profile_options(self) -> list[tuple[str, str]]:
        return [(p.stem, p.stem) for p in list_profiles()]

    def _refresh_profiles(self) -> None:
        sel: Select = self.query_one("#config-profile-select")
        options = self._profile_options()
        sel.set_options(options)

    def _load_profile(self) -> None:
        sel: Select = self.query_one("#config-profile-select")
        v = sel.value
        if not v or v is Select.BLANK:
            return
        try:
            cfg = load_profile(str(v))
            self._populate_form(cfg)
        except Exception as exc:
            self.notify(f"Hiba: {exc}", severity="error")

    def _save_profile(self) -> None:
        name_inp: Input = self.query_one("#cfg-profile-name-input")
        name = name_inp.value.strip()
        if not name:
            self.notify("Add meg a profil nevét!", severity="warning")
            return
        cfg = self._build_config()
        try:
            save_profile(cfg, name)
            self._refresh_profiles()
            self.notify(f"Profil mentve: {name}", severity="information")
        except Exception as exc:
            self.notify(f"Mentési hiba: {exc}", severity="error")

    def _populate_form(self, cfg: DeviceConfig) -> None:
        def _set(widget_id: str, value: str) -> None:
            try:
                inp: Input = self.query_one(widget_id)
                inp.value = value
            except Exception:
                pass

        _set("#cfg-ssid1", cfg.wifi.ssid1)
        _set("#cfg-pass1", cfg.wifi.password1)
        _set("#cfg-ssid2", cfg.wifi.ssid2)
        _set("#cfg-pass2", cfg.wifi.password2)
        _set("#cfg-mqtt-host", cfg.mqtt.host)
        _set("#cfg-mqtt-port", str(cfg.mqtt.port))
        _set("#cfg-mqtt-user", cfg.mqtt.user)
        _set("#cfg-mqtt-pass", cfg.mqtt.password)
        _set("#cfg-mqtt-topic", cfg.mqtt.topic)
        _set("#cfg-mqtt-fulltopic", cfg.mqtt.full_topic)
        _set("#cfg-topic", cfg.topic)
        _set("#cfg-teleperiod", str(cfg.tele_period))

        # Board / Module select
        try:
            mod_sel: Select = self.query_one("#cfg-module")
            mod_sel.value = cfg.module_type if cfg.module_type else D1_MINI.name
        except Exception:
            pass

        # Load GPIO assignments and rebuild the visual diagram
        self._gpio_assignments = {int(k): v for k, v in cfg.gpio.items()}
        self._selected_gpio = None
        try:
            self.query_one("#gpio-pin-form").add_class("hidden")
            self.query_one("#gpio-config-placeholder").remove_class("hidden")
        except Exception:
            pass
        self.call_after_refresh(self._rebuild_board_diagram)

    # ------------------------------------------------------------------
    # Sending config
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Config fetch from device
    # ------------------------------------------------------------------

    async def _fetch_config_from_device(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#cfg-fetch-status")

        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat! (Serial tab → Csatlakozás)", severity="warning")
            return

        status_lbl.update("[yellow]Lekérés…[/yellow]")
        fetch_btn: Button = self.query_one("#cfg-fetch-btn")
        fetch_btn.disabled = True

        try:
            # Clear buffer so we only parse fresh responses
            serial_bridge.clear_buffer()

            # Send all status and config queries
            serial_bridge.send("Status 1")   # topic, module, full_topic
            await asyncio.sleep(0.4)
            serial_bridge.send("Status 5")   # active WiFi SSID, IP (no password)
            await asyncio.sleep(0.4)
            serial_bridge.send("Ssid1")      # configured SSID1 (regardless of active conn.)
            await asyncio.sleep(0.3)
            serial_bridge.send("Ssid2")      # configured SSID2 (backup network)
            await asyncio.sleep(0.3)
            serial_bridge.send("Status 6")   # MQTT host, port, user (no password)
            await asyncio.sleep(0.4)
            serial_bridge.send("Status 2")   # Firmware / chip hardware
            await asyncio.sleep(1.0)         # Wait for all responses to arrive

            lines = list(serial_bridge.line_buffer)
            filled: list[str] = []
            skipped: list[str] = []

            # --- Parse Status 1 (device info) --------------------------
            s1 = parse_status1(lines)
            if s1.get("topic"):
                self._set_input("#cfg-topic", s1["topic"])
                self._set_input("#cfg-mqtt-topic", s1["topic"])
                filled.append("Topic")
            if s1.get("full_topic"):
                self._set_input("#cfg-mqtt-fulltopic", s1["full_topic"])
                filled.append("FullTopic")
            if s1.get("module_type"):
                try:
                    from tasmota_manager.board_layouts import TASMOTA_MODULE_TO_BOARD
                    mod_id = int(s1["module_type"])
                    board_name = TASMOTA_MODULE_TO_BOARD.get(mod_id)
                    if board_name:
                        sel: Select = self.query_one("#cfg-module")
                        sel.value = board_name
                        filled.append(f"Modul → {board_name}")
                except Exception:
                    pass

            # --- Parse Ssid1 / Ssid2 (configured networks) -------------
            ssids = parse_ssids(lines)
            # Ssid1/Ssid2 responses take priority over Status 5 (active only)
            if ssids.get("ssid1"):
                self._set_input("#cfg-ssid1", ssids["ssid1"])
                filled.append("WiFi SSID1")
            elif parse_status5(lines).get("ssid1"):
                # Fallback: active SSID from Status 5
                self._set_input("#cfg-ssid1", parse_status5(lines)["ssid1"])
                filled.append("WiFi SSID1 (aktív)")
            if "ssid2" in ssids:
                self._set_input("#cfg-ssid2", ssids["ssid2"])
                if ssids["ssid2"]:
                    filled.append("WiFi SSID2")
                # empty string is fine – means no backup network configured
            skipped.append("WiFi jelszavak")   # never returned by Tasmota

            # --- Parse Status 6 (MQTT) ---------------------------------
            s6 = parse_status6(lines)
            if s6.get("mqtt_host"):
                self._set_input("#cfg-mqtt-host", s6["mqtt_host"])
                filled.append("MQTT Host")
            if s6.get("mqtt_port"):
                self._set_input("#cfg-mqtt-port", s6["mqtt_port"])
                filled.append("MQTT Port")
            if s6.get("mqtt_user"):
                self._set_input("#cfg-mqtt-user", s6["mqtt_user"])
                filled.append("MQTT User")
            skipped.append("MQTT jelszó")   # never returned

            # --- Parse Status 2 (chip/hardware detection) --------------
            chip = parse_status2(lines)
            if chip:
                serial_bridge.detected_chip = chip
                status_lbl.update(f"[green]● Chip: {chip}[/green]")
                filled.append(f"Chip: {chip}")
            else:
                status_lbl.update("[dim]Chip nem azonosítható[/dim]")

            # --- Summary notification ----------------------------------
            filled_str = ", ".join(filled) if filled else "–"
            skipped_str = ", ".join(skipped)
            self.notify(
                f"Feltöltve: {filled_str}\n"
                f"Nem elérhető (Tasmota biztonsági korlát): {skipped_str}",
                severity="information",
                timeout=8,
            )
            self._update_preview()

        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")
            self.notify(f"Lekérési hiba: {exc}", severity="error")
        finally:
            fetch_btn.disabled = False

    # ------------------------------------------------------------------
    # WiFi scan
    # ------------------------------------------------------------------

    async def _do_wifi_scan(self) -> None:
        """
        Trigger a Tasmota WiFi scan and populate the scan results Select.

        Protocol (two-step):
          1. WifiScan 1  → starts async scan on device, returns {"WifiScan":"Scanning"}
          2. Wait ~4 s for the device to finish scanning
          3. WifiScan    → fetch cached results, returns {"WiFiScan":{"NET1":{...},...}}

        MQTT lines with individual NET results are also captured from the buffer.
        """
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#wifi-scan-status")
        scan_btn: Button = self.query_one("#wifi-scan-btn")

        if not serial_bridge.is_connected:
            self.notify(
                "Nincs soros port kapcsolat!\nCsatlakozz a Serial tabon, majd próbáld újra.",
                severity="warning",
            )
            return

        scan_btn.disabled = True
        results_panel = self.query_one("#wifi-scan-results")
        results_panel.add_class("hidden")

        try:
            # Start the scan – results arrive AUTOMATICALLY as individual
            # RSL: RESULT = {"WiFiScan":{"NET1":{...}}} lines after scan completes.
            # There is NO need to send a second query; just wait for the device.
            serial_bridge.clear_buffer()
            serial_bridge.send("WifiScan 1")

            # Poll the buffer every 0.5 s; give up after SCAN_TIMEOUT seconds.
            # Once the first NET result arrives, wait one extra second for the
            # remaining networks before declaring the scan complete.
            SCAN_TIMEOUT = 10.0
            SETTLE_AFTER_FIRST = 1.5   # wait this long after first result
            CHECK_INTERVAL    = 0.5

            elapsed = 0.0
            first_result_at: Optional[float] = None

            while elapsed < SCAN_TIMEOUT:
                await asyncio.sleep(CHECK_INTERVAL)
                elapsed += CHECK_INTERVAL

                lines   = list(serial_bridge.line_buffer)
                networks = parse_wifi_scan(lines)

                if networks:
                    if first_result_at is None:
                        first_result_at = elapsed
                    status_lbl.update(
                        f"[yellow]{len(networks)} hálózat eddig – várakozás…[/yellow]"
                    )
                    # Stop 1.5 s after the first result to collect stragglers
                    if elapsed - first_result_at >= SETTLE_AFTER_FIRST:
                        break
                else:
                    remaining = int(SCAN_TIMEOUT - elapsed)
                    status_lbl.update(
                        f"[yellow]Szkennelés… ({remaining} mp hátra)[/yellow]"
                    )

            # Final parse of everything collected
            lines    = list(serial_bridge.line_buffer)
            networks = parse_wifi_scan(lines)
            scan_sel: Select = self.query_one("#wifi-scan-select")

            if not networks:
                status_lbl.update("[red]Nem találtam hálózatot (próbáld újra)[/red]")
            else:
                options = [
                    (f"{n['ssid']}  ({n['rssi']} dBm, {n['enc']})", n["ssid"])
                    for n in networks
                ]
                scan_sel.set_options(options)
                results_panel.remove_class("hidden")
                status_lbl.update(
                    f"[green]{len(networks)} hálózat találva[/green]"
                )

        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")
        finally:
            scan_btn.disabled = False

    def _pick_wifi_to_input(self, btn_id: str) -> None:
        """Copy the selected scanned SSID into the SSID1 or SSID2 input."""
        scan_sel: Select = self.query_one("#wifi-scan-select")
        if scan_sel.value is Select.BLANK:
            self.notify("Előbb válassz hálózatot a listából!", severity="warning")
            return
        ssid = str(scan_sel.value)
        target = "#cfg-ssid1" if btn_id == "wifi-pick-ssid1" else "#cfg-ssid2"
        self._set_input(target, ssid)
        inp: Input = self.query_one(target)
        inp.focus()
        self.notify(
            f"SSID beállítva: {ssid}",
            severity="information",
        )

    def _set_input(self, widget_id: str, value: str) -> None:
        try:
            inp: Input = self.query_one(widget_id)
            inp.value = value
        except Exception:
            pass

    def _send_via_serial(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat!", severity="warning")
            return
        cfg = self._build_config()
        cmds = cfg.to_tasmota_commands()   # list of (cmd, val) tuples

        # Split into two phases to avoid overflowing Tasmota's ~256-byte serial buffer.
        #
        # Phase 1 – WiFi / MQTT / TelePeriod – sent individually (safe, no restart risk)
        # Phase 2 – Module + GPIO + Restart  – sent as a short Backlog0 so that the
        #            Module command cannot trigger an early restart before GPIO commands
        #            are processed (Backlog0 delays the restart until the last item).

        _GPIO_PREFIXES = ("GPIO",)
        _SKIP_SOLO     = {"Module", "Restart"}

        phase1: list[str] = []
        module_cmd: str   = ""
        gpio_cmds:  list[str] = []

        for cmd, val in cmds:
            full = f"{cmd} {val}"
            if cmd == "Module":
                module_cmd = full
            elif cmd.startswith("GPIO"):
                gpio_cmds.append(full)
            elif cmd == "Restart":
                pass   # handled in phase 2
            else:
                phase1.append(full)

        # Phase 2: short Backlog0 – only Module + GPIO + Restart
        backlog_parts: list[str] = []
        if module_cmd:
            backlog_parts.append(module_cmd)
        backlog_parts.extend(gpio_cmds)
        backlog_parts.append("Restart 1")
        backlog_cmd = "Backlog0 " + "; ".join(backlog_parts)

        try:
            # Phase 1: send WiFi / MQTT / general settings individually
            if phase1:
                serial_bridge.comm.send_config_block(phase1, delay=0.2)

            # Phase 2: atomic Module + GPIO + Restart
            serial_bridge.send(backlog_cmd)

            gpio_count = len(gpio_cmds)
            self.notify(
                f"Konfig elküldve: {len(phase1)} alap parancs + "
                f"Backlog({gpio_count} GPIO + Module + Restart)",
                severity="information",
            )
            self.app.sync_gpio_to_board()  # type: ignore[attr-defined]
        except Exception as exc:
            self.notify(f"Hiba: {exc}", severity="error")

    def _send_via_mqtt(self) -> None:
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        if not mqtt_mgr.connected:
            self.notify("Nincs MQTT kapcsolat!", severity="warning")
            return
        cfg = self._build_config()
        topic = cfg.mqtt.topic or cfg.topic
        if not topic:
            self.notify("Nincs topic megadva!", severity="warning")
            return
        for cmd, val in cfg.to_tasmota_commands():
            if cmd == "Restart":
                continue
            mqtt_topic = f"cmnd/{topic}/{cmd}"
            mqtt_mgr.publish(mqtt_topic, val)
        self.app.sync_gpio_to_board()  # type: ignore[attr-defined]
        mqtt_mgr.publish(f"cmnd/{topic}/Restart", "1")
        self.notify(f"Konfig elküldve MQTT-n: cmnd/{topic}/…", severity="information")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

