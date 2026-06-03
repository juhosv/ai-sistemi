"""Configuration tab – WiFi, MQTT, GPIO setup with profile management."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    Select,
    Static,
    TabPane,
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


class GpioRow(Vertical):
    """A single GPIO assignment row: pin label + function select + info."""

    def __init__(self, gpio_num: int, type_id: str = "none", *, chip: str = "ESP8266") -> None:
        super().__init__(classes="gpio-row-container")
        self._gpio_num = gpio_num
        self._type_id = type_id
        self._chip = chip

    def compose(self) -> ComposeResult:
        d_alias = self._d_alias()
        if d_alias:
            pin_label = f"GPIO{self._gpio_num} ({d_alias}):"
        else:
            pin_label = f"GPIO{self._gpio_num}:"

        # Filter out separator entries from options
        real_options = [
            (lbl, val) for lbl, val in _GPIO_SELECT_OPTIONS
            if not val.startswith("__sep_")
        ]

        with Horizontal(classes="gpio-row"):
            yield Label(pin_label, classes="gpio-pin-label")
            yield Select(
                options=real_options,
                value=self._type_id,
                id=f"gpio-sel-{self._gpio_num}",
                classes="gpio-select",
                allow_blank=False,
            )
            yield Label("", id=f"gpio-badge-{self._gpio_num}", classes="gpio-instance-badge")
            yield Button("✕", id=f"gpio-del-{self._gpio_num}", variant="error")

        yield Label("", id=f"gpio-hint-{self._gpio_num}", classes="gpio-hint")
        yield Label("", id=f"gpio-mqtt-hint-{self._gpio_num}", classes="gpio-mqtt-hint")

    def _d_alias(self) -> str:
        aliases = {16: "D0", 5: "D1", 4: "D2", 0: "D3", 2: "D4",
                   14: "D5", 12: "D6", 13: "D7", 15: "D8"}
        return aliases.get(self._gpio_num, "") if self._chip == "ESP8266" else ""

    @property
    def gpio_num(self) -> int:
        return self._gpio_num


class ConfigTab(TabPane):
    """Full device configuration editor."""

    DEFAULT_CSS = ""
    _current_gpio_rows: list[int] = []   # list of gpio numbers in order

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

            # --- Top panels: WiFi + MQTT --------------------------------
            with Horizontal(id="config-top-panels"):
                with Vertical(id="wifi-panel"):
                    yield Static("WiFi", classes="section-title")
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
                        yield Label("Modul:", classes="label")
                        yield Select(
                            options=[
                                ("Generic (18)", 18),
                                ("Sonoff Basic (1)", 1),
                                ("Sonoff S20 (8)", 8),
                                ("WeMos D1 Mini (18)", 18),
                            ],
                            value=18,
                            id="cfg-module",
                            allow_blank=False,
                        )

            # --- GPIO assignment ----------------------------------------
            with Vertical(id="gpio-panel"):
                yield Static("GPIO kiosztás", classes="section-title")
                yield Vertical(id="gpio-rows-container")
                with Horizontal(id="gpio-add-row"):
                    yield Label("Új GPIO:", classes="label")
                    yield Select(
                        options=self._gpio_num_options(),
                        id="gpio-new-num-select",
                        allow_blank=False,
                    )
                    yield Button("+ GPIO hozzáadása", id="gpio-add-btn", variant="default")

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
        table: DataTable = self.query_one("#config-preview-table")
        table.add_columns("Parancs", "Érték")
        self._update_preview()
        self._refresh_profiles()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "cfg-load-btn":
            self._load_profile()
        elif bid == "cfg-save-btn":
            self._save_profile()
        elif bid == "gpio-add-btn":
            self._add_gpio_row()
        elif bid.startswith("gpio-del-"):
            gpio_num = int(bid.split("-")[-1])
            self._remove_gpio_row(gpio_num)
        elif bid == "cfg-send-serial-btn":
            self._send_via_serial()
        elif bid == "cfg-send-mqtt-btn":
            self._send_via_mqtt()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id and event.select.id.startswith("gpio-sel-"):
            self._update_gpio_hints()
            self._update_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_preview()

    # ------------------------------------------------------------------
    # GPIO management
    # ------------------------------------------------------------------

    def _add_gpio_row(self) -> None:
        sel: Select = self.query_one("#gpio-new-num-select")
        v = sel.value
        if v is Select.BLANK:
            return
        gpio_num = int(v)
        if gpio_num in self._current_gpio_rows:
            return
        self._current_gpio_rows.append(gpio_num)
        container: Vertical = self.query_one("#gpio-rows-container")
        row = GpioRow(gpio_num, "none")
        container.mount(row)
        self._update_gpio_hints()
        self._update_preview()

    def _remove_gpio_row(self, gpio_num: int) -> None:
        if gpio_num in self._current_gpio_rows:
            self._current_gpio_rows.remove(gpio_num)
        try:
            rows = self.query(GpioRow)
            for row in rows:
                if row.gpio_num == gpio_num:
                    row.remove()
                    break
        except Exception:
            pass
        self._update_gpio_hints()
        self._update_preview()

    def _get_gpio_assignments(self) -> dict[int, str]:
        result: dict[int, str] = {}
        for gpio_num in self._current_gpio_rows:
            try:
                sel: Select = self.query_one(f"#gpio-sel-{gpio_num}")
                v = sel.value
                if v and v is not Select.BLANK:
                    result[gpio_num] = str(v)
            except Exception:
                pass
        return result

    def _update_gpio_hints(self) -> None:
        assignments = self._get_gpio_assignments()
        instances = compute_gpio_instances(assignments)
        codes = assign_tasmota_codes(assignments)

        for gpio_num, type_id in assignments.items():
            gt = GPIO_TYPE_BY_ID.get(type_id)
            instance_name = instances.get(gpio_num, "")
            tasmota_code = codes.get(gpio_num, 0)

            try:
                badge: Label = self.query_one(f"#gpio-badge-{gpio_num}")
                badge.update(f"→ {instance_name}" if instance_name and type_id != "none" else "")
            except Exception:
                pass

            try:
                hint: Label = self.query_one(f"#gpio-hint-{gpio_num}")
                hint.update(gt.description if gt and gt.description else "")
            except Exception:
                pass

            try:
                mqtt_hint: Label = self.query_one(f"#gpio-mqtt-hint-{gpio_num}")
                if gt and gt.mqtt_example and type_id != "none":
                    n = instances.get(gpio_num, "?")
                    # Extract instance number suffix
                    num_part = "".join(c for c in n if c.isdigit()) or "1"
                    example = gt.mqtt_example.replace("{n}", num_part)
                    mqtt_hint.update(f"MQTT: {example}")
                else:
                    mqtt_hint.update("")
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

        # Reload GPIO rows
        container: Vertical = self.query_one("#gpio-rows-container")
        container.remove_children()
        self._current_gpio_rows.clear()

        for gpio_str, type_id in cfg.gpio.items():
            gpio_num = int(gpio_str)
            self._current_gpio_rows.append(gpio_num)
            container.mount(GpioRow(gpio_num, type_id))

        self._update_gpio_hints()
        self._update_preview()

    # ------------------------------------------------------------------
    # Sending config
    # ------------------------------------------------------------------

    def _send_via_serial(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat!", severity="warning")
            return
        cfg = self._build_config()
        cmds = cfg.to_tasmota_command_strings()
        try:
            serial_bridge.comm.send_config_block(cmds)
            self.notify(f"{len(cmds)} parancs elküldve soros porton.", severity="information")
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
        mqtt_mgr.publish(f"cmnd/{topic}/Restart", "1")
        self.notify(f"Konfig elküldve MQTT-n: cmnd/{topic}/…", severity="information")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _gpio_num_options(self) -> list[tuple[str, int]]:
        esp8266_gpios = [(f"GPIO{n} (D{d})", n) for n, d in
                         [(16, 0), (5, 1), (4, 2), (0, 3), (2, 4),
                          (14, 5), (12, 6), (13, 7), (15, 8)]]
        esp32_extra = [(f"GPIO{n}", n) for n in
                       [17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]]
        return esp8266_gpios + esp32_extra
