"""Configuration tab – WiFi, MQTT, GPIO setup with profile management."""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# GPIO parser and type resolver shared with the Board tab
from tasmota_manager.screens.board_screen import _parse_gpio_from_device, _to_type

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


def parse_fulltopic_from_mqt_lines(lines: list[str], device_topic: str) -> Optional[str]:
    """Extract FullTopic by analysing MQT: debug lines from the serial log.

    Tasmota 15 does not include FullTopic in StatusPRM, but the device logs
    every MQTT publish like:
        MQT: demo_region/demo_user/proba_123/stat/STATUS = {...}

    From this we reconstruct: demo_region/demo_user/%topic%/%prefix%/
    """
    if not device_topic:
        return None
    _KNOWN_PREFIXES = ("stat", "tele", "cmnd")
    for line in lines:
        # Look for lines containing "MQT: <topic> = "
        idx = line.find("MQT: ")
        if idx < 0:
            continue
        rest = line[idx + 5:]
        eq = rest.find(" = ")
        if eq < 0:
            continue
        mqtt_topic = rest[:eq].strip()
        # Find the prefix segment
        for prefix in _KNOWN_PREFIXES:
            marker = f"/{prefix}/"
            pos = mqtt_topic.find(marker)
            if pos < 0:
                continue
            path_before_prefix = mqtt_topic[:pos]  # e.g. demo_region/demo_user/proba_123
            # Remove device_topic suffix
            suffix = f"/{device_topic}"
            if path_before_prefix.endswith(suffix):
                group_path = path_before_prefix[: -len(suffix)]
                # group_path = "demo_region/demo_user"
                return f"{group_path}/%topic%/%prefix%/"
            # Maybe no group prefix (default format): device_topic/prefix/...
            if path_before_prefix == device_topic:
                return "%topic%/%prefix%/"
            break
    return None


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
    Parse Ssid1 / Ssid2 from several Tasmota response formats.

    Tasmota 15 returns:
        {"SSId1":"HomeNetwork"}   ← note: capital SS, capital I
        {"SSId2":"BackupNet"}

    Status 0 / Status 3 returns StatusLOG with SSId array:
        {"StatusLOG": {"SSId": ["HomeNetwork", "BackupNet"], ...}}

    Status 5 returns the ACTIVE connected SSID (StatusNET.SSId).
    """
    result: dict = {}
    for line in lines:
        data = _extract_json_block(line)
        if not data:
            continue

        # Individual Ssid1/Ssid2 command responses – Tasmota 15 uses SSId1/SSId2
        # Handle both cases (Ssid1 and SSId1) for forward/backward compatibility
        for key in ("Ssid1", "SSId1"):
            if key in data:
                v = data[key]
                if v:   # only store non-empty primary SSID
                    result["ssid1"] = v
        for key in ("Ssid2", "SSId2"):
            if key in data:
                result["ssid2"] = data[key]   # empty string = no backup configured

        # StatusLOG.SSId array from Status 0 / Status 3
        log_block = data.get("StatusLOG", {})
        if isinstance(log_block, dict) and "SSId" in log_block:
            ssid_arr = log_block["SSId"]
            if isinstance(ssid_arr, list):
                if len(ssid_arr) > 0 and ssid_arr[0]:
                    result.setdefault("ssid1", ssid_arr[0])
                if len(ssid_arr) > 1:
                    result.setdefault("ssid2", ssid_arr[1])

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
    DEFAULT_GPIO_ASSIGNMENTS,
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
from tasmota_manager.groups_manager import (
    add_region,
    add_user,
    build_fulltopic,
    delete_region,
    delete_user,
    get_region_name,
    get_user_name,
    list_regions,
    list_users,
    update_region,
    update_user,
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

            # --- Profile + action row -----------------------------------
            with Horizontal(id="config-profile-row"):
                yield Label("Profil:", classes="cfg-row-label")
                yield Select(
                    options=self._profile_options(),
                    id="config-profile-select",
                    allow_blank=True,
                )
                yield Button("📂 Betöltés", id="cfg-load-btn", variant="default")
                yield Button("💾 Mentés", id="cfg-save-btn", variant="primary")
                yield Input(placeholder="Profil neve", id="cfg-profile-name-input", value="uj_profil")
                yield Button("↺ Reset", id="cfg-reset-btn", variant="error")

            # --- Group row (Régió / User) --------------------------------
            with Horizontal(id="config-group-row"):
                yield Label("Régió:", classes="cfg-row-label")
                yield Select(
                    options=self._region_options(),
                    id="cfg-region-select",
                    allow_blank=True,
                    prompt="– válassz régiót –",
                )
                yield Label("User:", classes="cfg-row-label")
                yield Select(
                    options=[],
                    id="cfg-user-select",
                    allow_blank=True,
                    prompt="– válassz usert –",
                )
                yield Button("⚙ Szerkesztés", id="cfg-groups-edit-btn", variant="default")

            # --- Group editor panel (hidden by default) ------------------
            with Vertical(id="cfg-groups-editor", classes="hidden"):
                yield Static("Csoportok kezelése", classes="section-title")
                with Horizontal(id="cfg-groups-editor-inner"):
                    # Left: region management
                    with Vertical(id="cfg-groups-region-col"):
                        yield Static("Régiók", classes="subsection-title")
                        yield Select(
                            options=self._region_options(),
                            id="cfg-edit-region-select",
                            allow_blank=True,
                            prompt="– válassz régiót –",
                        )
                        with Horizontal(classes="row"):
                            yield Input(placeholder="Régió azonosító (pl. hu_eszak)", id="cfg-new-region-id")
                            yield Input(placeholder="Megjelenítendő név", id="cfg-new-region-name")
                            yield Button("+ Hozzáad", id="cfg-add-region-btn", variant="success")
                        with Horizontal(classes="row"):
                            yield Button("🗑 Régió törlése", id="cfg-del-region-btn", variant="error")
                            yield Button("✦ Új régió", id="cfg-new-region-btn", variant="default")
                    # Right: user management
                    with Vertical(id="cfg-groups-user-col"):
                        yield Static("Userek (kiválasztott régióban)", classes="subsection-title")
                        yield Select(
                            options=[],
                            id="cfg-edit-user-select",
                            allow_blank=True,
                            prompt="– válassz usert –",
                        )
                        with Horizontal(classes="row"):
                            yield Input(placeholder="User azonosító (pl. juhosv)", id="cfg-new-user-id")
                            yield Input(placeholder="Megjelenítendő név", id="cfg-new-user-name")
                            yield Button("+ Hozzáad", id="cfg-add-user-btn", variant="success")
                        with Horizontal(classes="row"):
                            yield Button("🗑 User törlése", id="cfg-del-user-btn", variant="error")
                            yield Button("✦ Új user", id="cfg-new-user-btn", variant="default")

            # --- Device fetch row ---------------------------------------
            with Horizontal(id="config-fetch-row"):
                yield Button(
                    "📥 Konfiguráció letöltése az eszközről",
                    id="cfg-fetch-btn",
                    variant="warning",
                )
                yield Label("", id="cfg-fetch-hint", classes="hint")
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
                        yield Label("Eszköz azonosító:", classes="label")
                        yield Input(placeholder="pl. AABBCCDD (alapért. MAC)", id="cfg-mqtt-topic")
                    with Horizontal(classes="row"):
                        yield Label("FullTopic:", classes="label")
                        yield Input(value="%prefix%/%topic%/", id="cfg-mqtt-fulltopic")
                    yield Label("", id="cfg-fulltopic-preview", classes="hint")

            # --- General settings ---------------------------------------
            with Horizontal(id="general-panel"):
                with Vertical(id="general-left"):
                    yield Static("Általános", classes="section-title")
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

            # --- HTTP backup / restore ----------------------------------
            with Horizontal(id="config-backup-row"):
                yield Button("💾 Konfig backup", id="cfg-backup-btn", variant="default")
                yield Select(
                    options=[("– nincs backup fájl –", "__none")],
                    id="cfg-restore-select",
                    allow_blank=False,
                )
                yield Button("📤 Visszatöltés", id="cfg-restore-btn", variant="warning")
                yield Button("📋 Betöltés backup-ból", id="cfg-load-from-dmp-btn", variant="default")
                yield Label("", id="cfg-backup-status")

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
        self._refresh_backup_list()
        self._rebuild_board_diagram()
        # Update serial hint every second
        self.set_interval(1.0, self._update_fetch_hint)
        self._update_fetch_hint()

    def _update_fetch_hint(self) -> None:
        """Show/hide serial connection hint based on current connection state."""
        try:
            serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
            lbl: Label = self.query_one("#cfg-fetch-hint")
            if serial_bridge.is_connected:
                lbl.update("")
            else:
                lbl.update("[dim]  Soros portkapcsolat szükséges (Serial tab → Csatlakozás)[/dim]")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "cfg-load-btn":
            self._load_profile()
        elif bid == "cfg-save-btn":
            self._save_profile()
        elif bid == "cfg-reset-btn":
            self._reset_config()
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
        elif bid == "cfg-backup-btn":
            self.run_worker(self._do_backup(), name="cfg_backup")
        elif bid == "cfg-restore-btn":
            self.run_worker(self._do_restore(), name="cfg_restore")
        elif bid == "cfg-load-from-dmp-btn":
            self.run_worker(self._do_load_from_dmp(), name="cfg_load_dmp")
        # --- Group editor buttons ---
        elif bid == "cfg-groups-edit-btn":
            self._toggle_groups_editor()
        elif bid == "cfg-add-region-btn":
            self._add_region()
        elif bid == "cfg-del-region-btn":
            self._delete_region()
        elif bid == "cfg-add-user-btn":
            self._add_user()
        elif bid == "cfg-del-user-btn":
            self._delete_user()
        elif bid == "cfg-new-region-btn":
            self._clear_region_fields()
            try:
                self.query_one("#cfg-edit-region-select", Select).value = Select.BLANK
            except Exception:
                pass
        elif bid == "cfg-new-user-btn":
            self._clear_user_fields()
            try:
                self.query_one("#cfg-edit-user-select", Select).value = Select.BLANK
            except Exception:
                pass

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.select.id or ""
        if sid == "cfg-module":
            self._apply_module_defaults(str(event.value))
            self._rebuild_board_diagram()
            self._update_preview()
        elif sid == "gpio-func-select":
            self._update_func_preview()
        elif sid == "cfg-region-select":
            self._on_region_changed(event.value)
            self._update_fulltopic_from_group()
            try:
                self.app.sync_mqtt_to_monitor(topic_only=True)  # type: ignore[attr-defined]
            except Exception:
                pass
        elif sid == "cfg-user-select":
            self._update_fulltopic_from_group()
            try:
                self.app.sync_mqtt_to_monitor(topic_only=True)  # type: ignore[attr-defined]
            except Exception:
                pass
        elif sid == "cfg-edit-region-select":
            self._on_edit_region_changed(event.value)
        elif sid == "cfg-edit-user-select":
            region_sel: Select = self.query_one("#cfg-edit-region-select")
            rid = region_sel.value
            region_id = rid if isinstance(rid, str) else ""
            self._on_edit_user_changed(event.value, region_id)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_preview()
        if event.input.id == "cfg-mqtt-topic":
            try:
                region_sel: Select = self.query_one("#cfg-region-select")
                user_sel: Select = self.query_one("#cfg-user-select")
                rid = region_sel.value if isinstance(region_sel.value, str) else ""
                uid = user_sel.value if isinstance(user_sel.value, str) else ""
                self._update_fulltopic_preview(rid, uid)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Group (region/user) management helpers
    # ------------------------------------------------------------------

    def _region_options(self) -> list[tuple[str, str]]:
        return [(name, rid) for rid, name in list_regions()]

    def _user_options(self, region_id: str) -> list[tuple[str, str]]:
        return [(name, uid) for uid, name in list_users(region_id)]

    def _toggle_groups_editor(self) -> None:
        editor = self.query_one("#cfg-groups-editor")
        editor.toggle_class("hidden")
        btn: Button = self.query_one("#cfg-groups-edit-btn")
        if editor.has_class("hidden"):
            btn.label = "⚙ Szerkesztés"
            btn.variant = "default"
        else:
            btn.label = "✕ Bezárás"
            btn.variant = "warning"
            self._refresh_editor_region_select()

    def _on_region_changed(self, region_id) -> None:
        """Update user dropdown when region selection changes."""
        if region_id is None or region_id is Select.BLANK or not isinstance(region_id, str):
            self.query_one("#cfg-user-select", Select).set_options([])
            return
        self.query_one("#cfg-user-select", Select).set_options(self._user_options(region_id))

    def _on_edit_region_changed(self, region_id) -> None:
        """Update user dropdown in the editor panel and fill edit fields."""
        if region_id is None or region_id is Select.BLANK or not isinstance(region_id, str):
            self.query_one("#cfg-edit-user-select", Select).set_options([])
            self.query_one("#cfg-new-region-id", Input).value = ""
            self.query_one("#cfg-new-region-name", Input).value = ""
            self._set_region_btn_mode("add")
            return
        # Fill inputs with selected region's data
        self.query_one("#cfg-new-region-id", Input).value = region_id
        self.query_one("#cfg-new-region-name", Input).value = get_region_name(region_id)
        self._set_region_btn_mode("edit")
        self.query_one("#cfg-edit-user-select", Select).set_options(self._user_options(region_id))
        # Reset user fields when region changes
        self.query_one("#cfg-new-user-id", Input).value = ""
        self.query_one("#cfg-new-user-name", Input).value = ""
        self._set_user_btn_mode("add")

    def _on_edit_user_changed(self, user_id, region_id: str) -> None:
        """Fill user edit fields when a user is selected."""
        if user_id is None or user_id is Select.BLANK or not isinstance(user_id, str):
            self.query_one("#cfg-new-user-id", Input).value = ""
            self.query_one("#cfg-new-user-name", Input).value = ""
            self._set_user_btn_mode("add")
            return
        self.query_one("#cfg-new-user-id", Input).value = user_id
        self.query_one("#cfg-new-user-name", Input).value = get_user_name(region_id, user_id)
        self._set_user_btn_mode("edit")

    def _set_region_btn_mode(self, mode: str) -> None:
        btn: Button = self.query_one("#cfg-add-region-btn")
        if mode == "edit":
            btn.label = "💾 Mentés"
            btn.variant = "primary"
        else:
            btn.label = "+ Hozzáad"
            btn.variant = "success"

    def _set_user_btn_mode(self, mode: str) -> None:
        btn: Button = self.query_one("#cfg-add-user-btn")
        if mode == "edit":
            btn.label = "💾 Mentés"
            btn.variant = "primary"
        else:
            btn.label = "+ Hozzáad"
            btn.variant = "success"

    def _apply_fulltopic_to_group_selects(self, full_topic: str) -> None:
        """Parse FullTopic and set region/user dropdowns if values are recognised.

        Supports format: {region}/{user}/%topic%/%prefix%/
        Ignores default Tasmota format: %prefix%/%topic%/
        """
        import re as _re
        # Match: something/something/%topic%/%prefix%/ (our format)
        m = _re.match(r'^([^%/]+)/([^%/]+)/%topic%/%prefix%/', full_topic)
        if not m:
            return
        region_id = m.group(1)
        user_id = m.group(2)
        # Check if region exists in groups.json
        known_regions = [rid for rid, _ in list_regions()]
        if region_id not in known_regions:
            self.notify(
                f"FullTopic-ban talált régió ({region_id}) nem szerepel a csoportokban.",
                severity="warning",
                timeout=6,
            )
            return
        # Set region dropdown (this triggers on_select_changed → _on_region_changed
        # which populates user options; we must set user value AFTER that refresh)
        try:
            region_sel: Select = self.query_one("#cfg-region-select")
            region_sel.value = region_id
            # Explicitly populate user options now (in case event fires async)
            self.query_one("#cfg-user-select", Select).set_options(
                self._user_options(region_id)
            )
        except Exception:
            return
        # Check if user exists in the region
        known_users = [uid for uid, _ in list_users(region_id)]
        if user_id not in known_users:
            self.notify(
                f"FullTopic-ban talált user ({user_id}) nem szerepel a(z) {region_id} régióban.",
                severity="warning",
                timeout=6,
            )
            return

        # Defer user value + FullTopic correction via a short timer so that
        # set_options() reactive update fully completes before we set the value.
        # call_after_refresh is too early on first load; 150 ms is reliable.
        def _apply_user() -> None:
            try:
                self.query_one("#cfg-user-select", Select).value = user_id
                # Re-apply the correct FullTopic (region change may have reset it)
                self._update_fulltopic_from_group()
            except Exception:
                pass

        self.set_timer(0.15, _apply_user)
        self.notify(
            f"Régió és user beállítva: {region_id} / {user_id}",
            severity="information",
            timeout=4,
        )

    def _update_fulltopic_from_group(self) -> None:
        """Rebuild the FullTopic input and preview when region/user/topic changes."""
        region_sel: Select = self.query_one("#cfg-region-select")
        user_sel: Select = self.query_one("#cfg-user-select")
        region_id = region_sel.value
        user_id = user_sel.value
        rid = region_id if isinstance(region_id, str) and region_id else ""
        uid = user_id if isinstance(user_id, str) and user_id else ""
        new_fulltopic = build_fulltopic(rid, uid)
        self.query_one("#cfg-mqtt-fulltopic", Input).value = new_fulltopic
        self._update_fulltopic_preview(rid, uid)

    def _update_fulltopic_preview(self, region_id: str = "", user_id: str = "") -> None:
        """Show a concrete example of the resulting MQTT topic."""
        try:
            device_id = self.query_one("#cfg-mqtt-topic", Input).value.strip() or "AABBCCDD"
            if region_id and user_id:
                example = f"[dim]Példa:[/dim] {region_id}/{user_id}/{device_id}/tele/SENSOR"
            else:
                example = f"[dim]Példa:[/dim] tele/{device_id}/SENSOR"
            self.query_one("#cfg-fulltopic-preview").update(example)
        except Exception:
            pass

    def _refresh_group_selects(self) -> None:
        """Reload region options in both the main row and the editor."""
        opts = self._region_options()
        self.query_one("#cfg-region-select", Select).set_options(opts)
        self._refresh_editor_region_select()

    def _refresh_editor_region_select(self) -> None:
        opts = self._region_options()
        try:
            self.query_one("#cfg-edit-region-select", Select).set_options(opts)
        except Exception:
            pass

    def _add_region(self) -> None:
        new_id = self.query_one("#cfg-new-region-id", Input).value.strip()
        new_name = self.query_one("#cfg-new-region-name", Input).value.strip()
        if not new_id:
            self.notify("Add meg a régió azonosítóját!", severity="warning")
            return
        sel: Select = self.query_one("#cfg-edit-region-select")
        selected_id = sel.value if isinstance(sel.value, str) else ""
        if selected_id:
            # Edit mode – update existing region
            if update_region(selected_id, new_id, new_name):
                self._clear_region_fields()
                self._refresh_group_selects()
                self.notify(f"Régió módosítva: {new_id}", severity="information")
            else:
                self.notify("Hiba: az azonosító már foglalt!", severity="error")
        else:
            # Add mode – create new region
            if add_region(new_id, new_name):
                self._clear_region_fields()
                self._refresh_group_selects()
                self.notify(f"Régió hozzáadva: {new_id}", severity="information")
            else:
                self.notify(f"Ez a régió már létezik: {new_id}", severity="warning")

    def _clear_region_fields(self) -> None:
        self.query_one("#cfg-new-region-id", Input).value = ""
        self.query_one("#cfg-new-region-name", Input).value = ""
        self._set_region_btn_mode("add")

    def _delete_region(self) -> None:
        sel: Select = self.query_one("#cfg-edit-region-select")
        rid = sel.value
        if not isinstance(rid, str) or not rid:
            self.notify("Válassz régiót a törléshez!", severity="warning")
            return
        if delete_region(rid):
            self._refresh_group_selects()
            self.notify(f"Régió törölve: {rid}", severity="information")
        else:
            self.notify("A régió nem található!", severity="error")

    def _add_user(self) -> None:
        region_sel: Select = self.query_one("#cfg-edit-region-select")
        rid = region_sel.value
        if not isinstance(rid, str) or not rid:
            self.notify("Először válassz régiót!", severity="warning")
            return
        new_uid = self.query_one("#cfg-new-user-id", Input).value.strip()
        new_uname = self.query_one("#cfg-new-user-name", Input).value.strip()
        if not new_uid:
            self.notify("Add meg a user azonosítóját!", severity="warning")
            return
        user_sel: Select = self.query_one("#cfg-edit-user-select")
        selected_uid = user_sel.value if isinstance(user_sel.value, str) else ""
        if selected_uid:
            # Edit mode – update existing user
            if update_user(rid, selected_uid, new_uid, new_uname):
                self._clear_user_fields()
                self.query_one("#cfg-edit-user-select", Select).set_options(self._user_options(rid))
                self.notify(f"User módosítva: {new_uid}", severity="information")
            else:
                self.notify("Hiba: az azonosító már foglalt!", severity="error")
        else:
            # Add mode – create new user
            if add_user(rid, new_uid, new_uname):
                self._clear_user_fields()
                self.query_one("#cfg-edit-user-select", Select).set_options(self._user_options(rid))
                self.notify(f"User hozzáadva: {new_uid}", severity="information")
            else:
                self.notify(f"Ez a user már létezik: {new_uid}", severity="warning")

    def _clear_user_fields(self) -> None:
        self.query_one("#cfg-new-user-id", Input).value = ""
        self.query_one("#cfg-new-user-name", Input).value = ""
        self._set_user_btn_mode("add")

    def _delete_user(self) -> None:
        region_sel: Select = self.query_one("#cfg-edit-region-select")
        rid = region_sel.value
        user_sel: Select = self.query_one("#cfg-edit-user-select")
        uid = user_sel.value
        if not isinstance(rid, str) or not rid:
            self.notify("Válassz régiót!", severity="warning")
            return
        if not isinstance(uid, str) or not uid:
            self.notify("Válassz usert a törléshez!", severity="warning")
            return
        if delete_user(rid, uid):
            self._on_edit_region_changed(rid)
            self.notify(f"User törölve: {uid}", severity="information")
        else:
            self.notify("A user nem található!", severity="error")

    # ------------------------------------------------------------------
    # GPIO management – interactive board diagram
    # ------------------------------------------------------------------

    def _get_gpio_assignments(self) -> dict[int, str]:
        """Return current GPIO assignments, excluding unset ('none') pins."""
        return {k: v for k, v in self._gpio_assignments.items() if v and v != "none"}

    def clear_device_data(self) -> None:
        """Reset device-specific state (called when a new serial connection is made)."""
        self._gpio_assignments = {}
        self._selected_gpio = None
        self._rebuild_board_diagram()

    def _get_current_board(self) -> Optional[BoardLayout]:
        """Return the BoardLayout matching the currently selected module."""
        try:
            sel: Select = self.query_one("#cfg-module")
            if sel.value is not Select.BLANK:
                return BOARD_BY_NAME.get(str(sel.value))
        except Exception:
            pass
        return None

    def _apply_module_defaults(self, module_name: str) -> None:
        """Replace _gpio_assignments with the factory defaults for *module_name*.

        Generic boards (Wemos D1 Mini, ESP32 DevKit…) have an empty default
        so selecting them clears any previous assignment from another device.
        Unknown names are silently ignored – existing assignments stay intact.
        """
        if module_name not in DEFAULT_GPIO_ASSIGNMENTS:
            return
        self._gpio_assignments = dict(DEFAULT_GPIO_ASSIGNMENTS[module_name])
        # Clear the currently selected GPIO so the detail panel doesn't show
        # stale data for a pin that may not exist on the new board.
        self._selected_gpio = None
        try:
            self.query_one("#pin-config-form").display = False
        except Exception:
            pass

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
                # No dedicated board layout for this module (e.g. Sonoff devices).
                # Refresh the colors on whatever diagram is currently shown.
                self._refresh_all_diagram_pins()
                self._update_preview()
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

    def _refresh_all_diagram_pins(self) -> None:
        """Refresh every pin color on the current diagram to match _gpio_assignments.

        Called when switching to a module that has no dedicated BoardLayout (e.g.
        Sonoff devices). The existing diagram stays mounted but all its pin buttons
        are re-colored: assigned pins turn green, previously-assigned-but-now-clear
        pins revert to default.
        """
        try:
            diag: InteractiveBoardDiagram = self.query_one(InteractiveBoardDiagram)
        except Exception:
            return
        for pin in diag._layout.pins:
            if pin.gpio is None or pin.is_power or pin.is_uart or pin.adc_only:
                continue
            type_id = self._gpio_assignments.get(pin.gpio, "none")
            diag.update_pin(pin.gpio, type_id)

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

        # Read region/user from dropdowns
        region_id = ""
        user_id = ""
        try:
            r = self.query_one("#cfg-region-select", Select).value
            region_id = r if isinstance(r, str) else ""
        except Exception:
            pass
        try:
            u = self.query_one("#cfg-user-select", Select).value
            user_id = u if isinstance(u, str) else ""
        except Exception:
            pass

        device_id = _val("#cfg-mqtt-topic")
        return DeviceConfig(
            device_name=device_id,
            topic=device_id,
            region_id=region_id,
            user_id=user_id,
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

    def _reset_config(self) -> None:
        """Reset all config fields to their default/empty state."""
        defaults = [
            ("#cfg-ssid1", ""), ("#cfg-pass1", ""),
            ("#cfg-ssid2", ""), ("#cfg-pass2", ""),
            ("#cfg-mqtt-host", "broker.emqx.io"),
            ("#cfg-mqtt-port", "1883"),
            ("#cfg-mqtt-user", ""), ("#cfg-mqtt-pass", ""),
            ("#cfg-mqtt-topic", ""),
            ("#cfg-mqtt-fulltopic", "%prefix%/%topic%/"),
            ("#cfg-teleperiod", "300"),
        ]
        for widget_id, value in defaults:
            try:
                self.query_one(widget_id, Input).value = value
            except Exception:
                pass
        # Reset module select
        try:
            self.query_one("#cfg-module", Select).value = D1_MINI.name
        except Exception:
            pass
        # Reset region/user selects
        try:
            self.query_one("#cfg-region-select", Select).value = Select.BLANK
            self.query_one("#cfg-user-select", Select).set_options([])
        except Exception:
            pass
        # Reset GPIO assignments and diagram
        self._gpio_assignments = {}
        self._selected_gpio = None
        self._rebuild_board_diagram()
        # Reset preview table
        try:
            table: DataTable = self.query_one("#config-preview-table")
            table.clear()
        except Exception:
            pass
        # Clear fetch status
        try:
            self.query_one("#cfg-fetch-status").update("")
        except Exception:
            pass
        self.notify("Konfiguráció alaphelyzetbe állítva.", severity="information")

    def _profile_options(self) -> list[tuple[str, str]]:
        return [(p.stem, p.stem) for p in list_profiles()]

    def _refresh_profiles(self) -> None:
        sel: Select = self.query_one("#config-profile-select")
        options = self._profile_options()
        sel.set_options(options)

    def _load_profile(self) -> None:
        sel: Select = self.query_one("#config-profile-select")
        v = sel.value
        # Guard against no selection (Select.BLANK, None, or non-string sentinels)
        if v is None or v is Select.BLANK or not isinstance(v, str) or not v.strip():
            options = self._profile_options()
            if not options:
                self.notify("Nincs mentett profil. Előbb mentsd el az aktuális konfigurációt!", severity="warning")
            else:
                self.notify("Válassz profilt a legördülő listából, majd kattints Betöltés-re!", severity="information")
            return
        try:
            cfg = load_profile(v)
            self._populate_form(cfg)
            self.notify(f"Profil betöltve: {v}", severity="information")
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
        _set("#cfg-mqtt-topic", cfg.mqtt.topic or cfg.topic)
        _set("#cfg-mqtt-fulltopic", cfg.mqtt.full_topic)
        _set("#cfg-teleperiod", str(cfg.tele_period))

        # Board / Module select
        try:
            mod_sel: Select = self.query_one("#cfg-module")
            mod_sel.value = cfg.module_type if cfg.module_type else D1_MINI.name
        except Exception:
            pass

        # Region / User dropdowns
        if cfg.region_id:
            try:
                region_sel: Select = self.query_one("#cfg-region-select")
                region_sel.value = cfg.region_id
                # Populate user dropdown for this region
                self._on_region_changed(cfg.region_id)
                if cfg.user_id:
                    self.query_one("#cfg-user-select", Select).value = cfg.user_id
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
        app = self.app  # type: ignore[attr-defined]
        bridge = app.http_bridge if app.http_bridge.is_connected else app.serial_bridge
        status_lbl: Label = self.query_one("#cfg-fetch-status")

        if not bridge.is_connected:
            self.notify("Nincs kapcsolat! (Serial tab → Csatlakozás / HTTP)", severity="warning")
            return

        status_lbl.update("[yellow]Lekérés…[/yellow]")
        fetch_btn: Button = self.query_one("#cfg-fetch-btn")
        fetch_btn.disabled = True

        try:
            # Clear buffer so we only parse fresh responses
            bridge.clear_buffer()

            # Send all status and config queries
            # Status 0 = full status dump; in Tasmota 15 Topic/Module are ONLY here
            app.send_cmd("Status 0")
            await asyncio.sleep(0.6)
            app.send_cmd("Status 1")   # StatusPRM (baudrate, OTA url, etc.)
            await asyncio.sleep(0.4)
            app.send_cmd("Status 5")   # active WiFi SSID, IP (no password)
            await asyncio.sleep(0.4)
            app.send_cmd("Ssid1")      # configured SSID1 (regardless of active conn.)
            await asyncio.sleep(0.3)
            app.send_cmd("Ssid2")      # configured SSID2 (backup network)
            await asyncio.sleep(0.3)
            app.send_cmd("Status 6")   # MQTT host, port, user (no password)
            await asyncio.sleep(0.4)
            app.send_cmd("Status 2")   # Firmware / chip hardware
            await asyncio.sleep(0.4)
            app.send_cmd("GPIO")       # GPIO function assignments
            await asyncio.sleep(1.0)   # Wait for all responses to arrive

            lines = list(bridge.line_buffer)
            filled: list[str] = []
            skipped: list[str] = []

            # --- Parse Status 1 (device info) --------------------------
            s1 = parse_status1(lines)
            if s1.get("topic"):
                self._set_input("#cfg-mqtt-topic", s1["topic"])
                filled.append("Topic")
            # --- Try to infer FullTopic from MQT: log lines ---------------
            # Tasmota 15 does not include FullTopic in StatusPRM, but the
            # device logs every MQTT publish (e.g. "MQT: region/user/topic/stat/STATUS")
            device_topic_for_ft = s1.get("topic", "")
            inferred_fulltopic = parse_fulltopic_from_mqt_lines(lines, device_topic_for_ft)
            if inferred_fulltopic:
                s1["full_topic"] = inferred_fulltopic

            if s1.get("full_topic"):
                full_topic = s1["full_topic"]
                self._set_input("#cfg-mqtt-fulltopic", full_topic)
                filled.append("FullTopic")
                # Try to extract region/user from the FullTopic
                # Expected format: {region}/{user}/%topic%/%prefix%/
                self._apply_fulltopic_to_group_selects(full_topic)
            if s1.get("module_type") is not None:   # Module 0 is valid (falsy in Python!)
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

            # --- Parse GPIO assignments ---------------------------------
            gpio_from_device = _parse_gpio_from_device(lines)
            if gpio_from_device:
                self._gpio_assignments = gpio_from_device
                self._rebuild_board_diagram()
                summary = ", ".join(
                    f"GPIO{g}={t}" for g, t in sorted(gpio_from_device.items())
                )
                filled.append(f"GPIO ({len(gpio_from_device)} pin): {summary}")

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
            # Push broker/topic settings to MQTT Monitor tab
            try:
                self.app.sync_mqtt_to_monitor()  # type: ignore[attr-defined]
            except Exception:
                pass

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
        app = self.app  # type: ignore[attr-defined]
        bridge = app.http_bridge if app.http_bridge.is_connected else app.serial_bridge
        status_lbl: Label = self.query_one("#wifi-scan-status")
        scan_btn: Button = self.query_one("#wifi-scan-btn")

        if not bridge.is_connected:
            self.notify(
                "Nincs kapcsolat!\nCsatlakozz a Serial tabon, majd próbáld újra.",
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
            bridge.clear_buffer()
            app.send_cmd("WifiScan 1")

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

                lines    = list(bridge.line_buffer)
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
            lines    = list(bridge.line_buffer)
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
        app = self.app  # type: ignore[attr-defined]
        serial_bridge = app.serial_bridge
        if not serial_bridge.is_connected and not app.http_bridge.is_connected:
            self.notify("Nincs kapcsolat! (Serial tab → Csatlakozás / HTTP)", severity="warning")
            return
        cfg = self._build_config()
        cmds = cfg.to_tasmota_commands()   # list of (cmd, val) tuples

        # CRITICAL: Tasmota restarts the device immediately when a Module command
        # is processed – even inside a Backlog.  Any commands after Module in the
        # same Backlog are lost.
        #
        # Strategy:
        #   Phase 1 – WiFi / MQTT / TelePeriod  → sent individually (no restart)
        #   Phase 2 – Module only (if needed)   → triggers device restart
        #             We wait ~6 s for the device to come back up.
        #   Phase 3 – GPIO + Restart             → sent as Backlog0 after reboot

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
                pass   # handled below
            else:
                phase1.append(full)

        # Build GPIO + Restart as a short Backlog0 (no Module here!)
        gpio_backlog: str = ""
        if gpio_cmds:
            gpio_backlog = "Backlog0 " + "; ".join(gpio_cmds) + "; Restart 1"

        self.app.run_worker(  # type: ignore[attr-defined]
            self._do_send_serial(
                phase1, module_cmd, gpio_backlog, len(gpio_cmds)
            ),
            exclusive=False,
        )

    async def _do_send_serial(
        self,
        phase1: list[str],
        module_cmd: str,
        gpio_backlog: str,
        gpio_count: int,
    ) -> None:
        """Async worker: sends config in phases, waiting for reboot if Module changes."""
        import asyncio as _asyncio

        app = self.app  # type: ignore[attr-defined]
        serial_bridge = app.serial_bridge

        try:
            # Phase 1: WiFi / MQTT / general settings individually
            if phase1:
                if serial_bridge.is_connected:
                    serial_bridge.comm.send_config_block(phase1, delay=0.2)
                else:
                    for cmd in phase1:
                        app.send_cmd(cmd)
                        await _asyncio.sleep(0.2)
                await _asyncio.sleep(0.5)

            # Phase 2: Module (if needed) – triggers reboot, wait for device to come back
            if module_cmd:
                app.send_cmd(module_cmd)
                self.notify(
                    "Module parancs elküldve – várakozás az újraindulásra (6 mp)…",
                    severity="information",
                    timeout=8,
                )
                await _asyncio.sleep(6.0)   # give device time to reboot

            # Phase 3: GPIO + Restart (Backlog0, no Module inside)
            if gpio_backlog:
                app.send_cmd(gpio_backlog)

            self.notify(
                f"Konfig elküldve: {len(phase1)} alap parancs"
                + (f" + Module" if module_cmd else "")
                + (f" + {gpio_count} GPIO + Restart" if gpio_backlog else ""),
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
    # HTTP backup / restore
    # ------------------------------------------------------------------

    @staticmethod
    def _backup_dir() -> "Path":
        from pathlib import Path
        from tasmota_manager.config_builder import PROFILES_DIR
        backup_dir = PROFILES_DIR.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        return backup_dir

    def _refresh_backup_list(self) -> None:
        """Refresh the restore Select with .dmp files from the backups/ folder."""
        try:
            files = sorted(self._backup_dir().glob("*.dmp"), reverse=True)
            sel: Select = self.query_one("#cfg-restore-select")
            if files:
                options = [(f.name, str(f)) for f in files]
            else:
                options = [("– nincs backup fájl –", "__none")]
            sel.set_options(options)
        except Exception:
            pass

    async def _do_backup(self) -> None:
        from datetime import datetime
        http_bridge = self.app.http_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#cfg-backup-status")

        if not http_bridge.is_connected:
            self.notify("HTTP kapcsolat szükséges a backuphoz!", severity="warning")
            return

        status_lbl.update("[yellow]Backup letöltése…[/yellow]")
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, http_bridge.download_config
            )
            if not data:
                status_lbl.update("[red]Sikertelen letöltés[/red]")
                self.notify("Backup letöltése sikertelen!", severity="error")
                return

            ip_short = http_bridge.ip.replace("http://", "").replace(".", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{ip_short}_{ts}.dmp"
            backup_path = self._backup_dir() / filename
            backup_path.write_bytes(data)

            status_lbl.update(f"[green]✓ {filename}  ({len(data)} byte)[/green]")
            self.notify(
                f"Backup mentve: {backup_path}",
                severity="information",
                timeout=10,
            )
            self._refresh_backup_list()
        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")

    async def _do_restore(self) -> None:
        http_bridge = self.app.http_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#cfg-backup-status")

        if not http_bridge.is_connected:
            self.notify("HTTP kapcsolat szükséges a visszatöltéshez!", severity="warning")
            return

        sel: Select = self.query_one("#cfg-restore-select")
        path_str = str(sel.value)
        if not path_str or path_str == "__none" or sel.value is Select.BLANK:
            self.notify("Nincs backup fájl kiválasztva!", severity="warning")
            return

        from pathlib import Path
        backup_path = Path(path_str)
        if not backup_path.exists():
            status_lbl.update("[red]Fájl nem található[/red]")
            return

        status_lbl.update("[yellow]Visszatöltés…[/yellow]")
        try:
            data = backup_path.read_bytes()
            ok = await asyncio.get_event_loop().run_in_executor(
                None, http_bridge.upload_config, data
            )
            if ok:
                status_lbl.update("[green]✓ Visszatöltve – az eszköz újraindul[/green]")
                self.notify(
                    f"Konfig visszatöltve ({backup_path.name}). Az eszköz újraindul.",
                    severity="information",
                    timeout=8,
                )
            else:
                status_lbl.update("[red]Visszatöltés sikertelen[/red]")
                self.notify("Konfig visszatöltés sikertelen!", severity="error")
        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")

    # ------------------------------------------------------------------
    # DMP binary parse and multi-tab load
    # ------------------------------------------------------------------

    @staticmethod
    def _find_python() -> Optional[str]:
        """Find a usable Python interpreter.

        When running from source: use the current interpreter.
        When running from a PyInstaller exe: look for Python in PATH.
        """
        import shutil
        if not getattr(sys, "frozen", False):
            return sys.executable
        for candidate in ("python.exe", "python3.exe", "py.exe", "python3", "python"):
            found = shutil.which(candidate)
            if found:
                return found
        return None

    @staticmethod
    def _find_decode_script() -> Optional[Path]:
        """Locate decode_config_tool.py.

        Checks _MEIPASS (PyInstaller _internal/), next to the exe, and the
        development project root.
        """
        candidates: list[Path] = []
        # PyInstaller: resources are in sys._MEIPASS (_internal/)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "decode_config_tool.py")
        # Next to the exe (top-level dist folder)
        candidates.append(Path(sys.executable).parent / "decode_config_tool.py")
        # Development: three levels up from this file → tasmota-manager/
        candidates.append(Path(__file__).parent.parent.parent / "decode_config_tool.py")
        for p in candidates:
            if p.exists():
                return p
        return None

    async def _parse_dmp(self, dmp_path: Path) -> Optional[dict]:
        """Call decode_config_tool.py as subprocess and return parsed JSON."""
        python = self._find_python()
        if not python:
            self.notify(
                "Python interpreter nem található!\n"
                "Telepítsd a Pythont, hogy a backup parse-olás működjön.",
                severity="error", timeout=10,
            )
            return None
        script = self._find_decode_script()
        if not script:
            self.notify(
                "decode_config_tool.py nem található!\n"
                "Ellenőrizd, hogy a fájl az exe mellett van.",
                severity="error", timeout=10,
            )
            return None
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [python, str(script),
                     "-s", str(dmp_path.resolve()),   # plain path (not URI) for reliability
                     "-T", "json",
                     "-S",                            # force stdout output
                     "--json-show-pw",
                     "--json-indent", "-1"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            )
            if result.returncode not in (0, 1):  # 0=ok, 1=restore skipped (non-fatal)
                self.notify(
                    f"decode-config hiba (exit {result.returncode}):\n"
                    f"{(result.stderr or result.stdout)[:300]}",
                    severity="error", timeout=12,
                )
                return None
            stdout = result.stdout.strip()
            if not stdout:
                self.notify(
                    f"decode-config: üres kimenet\nstderr: {result.stderr[:300]}",
                    severity="error", timeout=12,
                )
                return None
            return json.loads(stdout)
        except Exception as exc:
            self.notify(f"Parse hiba: {exc}", severity="error")
            return None

    async def _do_load_from_dmp(self) -> None:
        """Load all fields from the selected .dmp backup into Config, Board, Rules tabs."""
        sel: Select = self.query_one("#cfg-restore-select")
        path_str = str(sel.value)
        if not path_str or path_str == "__none" or sel.value is Select.BLANK:
            self.notify("Nincs backup fájl kiválasztva!", severity="warning")
            return

        dmp_path = Path(path_str)
        if not dmp_path.exists():
            self.notify(f"Fájl nem található: {dmp_path}", severity="error")
            return

        status_lbl: Label = self.query_one("#cfg-backup-status")
        status_lbl.update("[yellow]Parse-olás…[/yellow]")

        data = await self._parse_dmp(dmp_path)
        if not data:
            status_lbl.update("[red]Parse sikertelen[/red]")
            return

        filled = self._apply_dmp_data(data)
        status_lbl.update(f"[green]✓ {dmp_path.name} betöltve ({filled} mező)[/green]")
        self.notify(
            f"Backup betöltve: {filled} mező kitöltve\n({dmp_path.name})",
            severity="information", timeout=8,
        )

    def _apply_dmp_data(self, data: dict) -> int:
        """Fill Config, Board and Rules tabs from a decoded .dmp dict.

        Returns the number of fields that were filled.
        """
        filled = 0

        def _s(val) -> str:
            return str(val) if val is not None else ""

        # --- WiFi ---
        sta_ssid = data.get("sta_ssid") or []
        sta_pwd  = data.get("sta_pwd")  or []
        if len(sta_ssid) > 0 and sta_ssid[0]:
            self._set_input("#cfg-ssid1", _s(sta_ssid[0]));  filled += 1
        if len(sta_ssid) > 1 and sta_ssid[1]:
            self._set_input("#cfg-ssid2", _s(sta_ssid[1]));  filled += 1
        if len(sta_pwd) > 0 and sta_pwd[0]:
            self._set_input("#cfg-pass1", _s(sta_pwd[0]));   filled += 1
        if len(sta_pwd) > 1 and sta_pwd[1]:
            self._set_input("#cfg-pass2", _s(sta_pwd[1]));   filled += 1

        # --- MQTT ---
        for key, widget_id in [
            ("mqtt_host",      "#cfg-mqtt-host"),
            ("mqtt_user",      "#cfg-mqtt-user"),
            ("mqtt_pwd",       "#cfg-mqtt-pass"),
            ("mqtt_topic",     "#cfg-mqtt-topic"),
            ("mqtt_fulltopic", "#cfg-mqtt-fulltopic"),
        ]:
            val = data.get(key)
            if val:
                self._set_input(widget_id, _s(val))
                filled += 1
        if data.get("mqtt_port"):
            self._set_input("#cfg-mqtt-port", _s(data["mqtt_port"]))
            filled += 1

        # --- TelePeriod ---
        if data.get("tele_period"):
            self._set_input("#cfg-teleperiod", _s(data["tele_period"]))
            filled += 1

        # --- GPIO assignments → Config tab + Board tab ---
        gpio_list = (
            data.get("gpio")
            or (data.get("user_template") or {}).get("gpio")
            or (data.get("user_template_esp32") or {}).get("gpio")
            or []
        )
        if gpio_list:
            gpio_assignments: dict[int, str] = {}
            for idx, code in enumerate(gpio_list):
                if isinstance(code, int) and code != 0:
                    type_id = _to_type(code)
                    if type_id and type_id != "none":
                        gpio_assignments[idx] = type_id
            if gpio_assignments:
                self._gpio_assignments = gpio_assignments
                filled += len(gpio_assignments)
                # Rebuild board diagram and push to Board tab
                self._rebuild_board_diagram()
                try:
                    self.app.sync_gpio_to_board()  # type: ignore[attr-defined]
                except Exception:
                    pass

        # --- Rules → Rules tab ---
        rules_list = data.get("rules") or []
        if rules_list:
            try:
                from tasmota_manager.screens.rules_screen import RulesTab
                rules_tab: RulesTab = self.app.query_one(RulesTab)  # type: ignore[attr-defined]
                rules_tab.load_rules_from_backup(rules_list)
                non_empty = sum(1 for r in rules_list if r)
                if non_empty:
                    filled += non_empty
            except Exception:
                pass

        return filled

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

