"""Rules tab – visual Tasmota Rule builder.

Each rule entry maps to one Tasmota  ON <trigger> DO [IF...] <cmd> [ELSE <cmd>] [ENDIF] ENDON  block.
Trigger options are derived automatically from the Config tab's GPIO assignments.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
    Static,
    TabPane,
    TextArea,
)


# ---------------------------------------------------------------------------
# Trigger / action catalogue
# ---------------------------------------------------------------------------

# Maps GPIO type_id → list of (label, tasmota_source) for trigger dropdown
_SENSOR_TRIGGERS: dict[str, list[tuple[str, str]]] = {
    "ds18b20": [
        ("DS18B20 – Hőmérséklet",  "DS18B20#Temperature"),
    ],
    "dht22": [
        ("DHT22 – Hőmérséklet",    "AM2301#Temperature"),
        ("DHT22 – Páratartalom",   "AM2301#Humidity"),
    ],
    "dht11": [
        ("DHT11 – Hőmérséklet",    "DHT11#Temperature"),
        ("DHT11 – Páratartalom",   "DHT11#Humidity"),
    ],
    "bme280": [
        ("BME280 – Hőmérséklet",   "BME280#Temperature"),
        ("BME280 – Páratartalom",  "BME280#Humidity"),
        ("BME280 – Légnyomás",     "BME280#Pressure"),
    ],
}

# Power/relay triggers derived from relay instance count
_RELAY_TRIGGER_TMPL  = ("Relay {n} állapot", "Power{n}#State")
_SWITCH_TRIGGER_TMPL = ("Switch {n} bement",  "Switch{n}#State")

# Always-available triggers
_FIXED_TRIGGERS: list[tuple[str, str]] = [
    ("Rendszer – Induláskor",   "System#Boot"),
    ("Rendszer – Mentéskor",    "System#Save"),
    ("WiFi – Csatlakozva",      "Wifi#Connected"),
    ("WiFi – Lecsatlakozva",    "Wifi#Disconnected"),
    ("MQTT – Csatlakozva",      "Mqtt#Connected"),
    ("Időzítő 1",               "Rules#Timer=1"),
    ("Időzítő 2",               "Rules#Timer=2"),
    ("Időzítő 3",               "Rules#Timer=3"),
    ("Időzítő 4",               "Rules#Timer=4"),
]

_COMPARISON_OPS: list[tuple[str, str]] = [
    (">",  ">"),
    ("<",  "<"),
    (">=", ">="),
    ("<=", "<="),
    ("=",  "="),
    ("!=", "!="),
]

_POWER_STATES: list[tuple[str, str]] = [
    ("BE (1)",  "1"),
    ("KI (0)", "0"),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RuleEntry:
    entry_id: int
    trigger_source: str = ""          # e.g. "DS18B20#Temperature"
    has_value: bool = True            # False for event-only triggers (System#Boot)
    operator: str = ">"
    trigger_value: str = "30"
    then_action: str = ""             # e.g. "Dimmer 80"
    else_action: str = ""             # empty = no ELSE branch
    # internal: widget-level data filled in from UI on generate
    _trigger_needs_value: bool = field(default=True, repr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _triggers_from_assignments(assignments: dict[int, str]) -> list[tuple[str, str]]:
    """Build trigger option list from Config tab GPIO assignments.

    Labels include the GPIO pin number so the user can identify the hardware pin,
    e.g. "Switch 1 bement (GPIO21)" or "Relay 1 állapot (GPIO32)".
    """
    options: list[tuple[str, str]] = []
    relay_count = 0
    switch_count = 0
    seen_sensor_srcs: set[str] = set()
    for gpio, type_id in sorted(assignments.items()):
        base = type_id.split("_")[0] if "_" in type_id else type_id
        pin_tag = f" (GPIO{gpio})"
        if base in _SENSOR_TRIGGERS:
            for label, src in _SENSOR_TRIGGERS[base]:
                if src not in seen_sensor_srcs:
                    seen_sensor_srcs.add(src)
                    options.append((label + pin_tag, src))
        elif base == "relay":
            relay_count += 1
            lbl, src_tmpl = _RELAY_TRIGGER_TMPL
            lbl2 = lbl.replace("{n}", str(relay_count)) + pin_tag
            src2 = src_tmpl.replace("{n}", str(relay_count))
            options.append((lbl2, src2))
        elif base == "switch":
            switch_count += 1
            lbl, src_tmpl = _SWITCH_TRIGGER_TMPL
            lbl2 = lbl.replace("{n}", str(switch_count)) + pin_tag
            src2 = src_tmpl.replace("{n}", str(switch_count))
            options.append((lbl2, src2))
    options.extend(_FIXED_TRIGGERS)
    return options


def _actions_from_assignments(assignments: dict[int, str]) -> list[tuple[str, str]]:
    """Build action option list from GPIO assignments.

    Labels include the GPIO pin number, e.g. "Relay 1 – BE (GPIO32)".
    """
    options: list[tuple[str, str]] = []
    relay_count = 0
    pwm_count = 0
    for gpio, type_id in sorted(assignments.items()):
        base = type_id.split("_")[0] if "_" in type_id else type_id
        pin_tag = f" (GPIO{gpio})"
        if base == "relay":
            relay_count += 1
            options.append((f"Relay {relay_count} – BE{pin_tag}",     f"Power{relay_count} ON"))
            options.append((f"Relay {relay_count} – KI{pin_tag}",     f"Power{relay_count} OFF"))
            options.append((f"Relay {relay_count} – VÁLTÁS{pin_tag}", f"Power{relay_count} TOGGLE"))
        elif base == "pwm":
            pwm_count += 1
            options.append((f"PWM {pwm_count} – Fényerő{pin_tag}",    f"__DIMMER_{pwm_count}"))
            options.append((f"PWM {pwm_count} – Direkt érték{pin_tag}", f"__PWM_{pwm_count}"))
    # Always available
    options.append(("Késleltetés (Delay)",    "__DELAY"))
    options.append(("Timer indítása",         "__TIMER"))
    options.append(("MQTT Publish",           "__PUBLISH"))
    return options


_TRIGGER_NEEDS_VALUE = {
    "System#Boot": False,
    "System#Save": False,
    "Wifi#Connected": False,
    "Wifi#Disconnected": False,
    "Mqtt#Connected": False,
}

def _trigger_needs_value(src: str) -> bool:
    return _TRIGGER_NEEDS_VALUE.get(src, not src.startswith("Rules#Timer"))


# Predefined selectable values for discrete triggers
_ONOFF_OPTIONS: list[tuple[str, str]] = [
    ("BE – 1",  "1"),
    ("KI – 0",  "0"),
]

def _get_trigger_value_options(src: str) -> Optional[list[tuple[str, str]]]:
    """Return preset dropdown options if the trigger has discrete values, else None.

    Switch#State and Power#State accept 0 (KI) or 1 (BE).
    Returns None for numeric/free-input triggers.
    """
    if not src:
        return None
    if "#State" in src and (src.startswith("Switch") or src.startswith("Power")):
        return _ONOFF_OPTIONS
    return None  # numeric / free input


# ---------------------------------------------------------------------------
# Rule Card widget
# ---------------------------------------------------------------------------

class RuleCard(Vertical):
    """One ON...ENDON rule entry with trigger + IF/ELSE actions."""

    def __init__(self, entry_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry_id = entry_id
        self._trigger_options: list[tuple[str, str]] = list(_FIXED_TRIGGERS)
        self._action_options: list[tuple[str, str]] = [
            ("Késleltetés (Delay)", "__DELAY"),
            ("Timer indítása",      "__TIMER"),
            ("MQTT Publish",        "__PUBLISH"),
        ]
        self._has_else = False

    def compose(self) -> ComposeResult:
        eid = self.entry_id
        with Horizontal(classes="rule-card-header"):
            yield Static(f"Szabály {eid}", classes="rule-card-title")
            yield Button("✕ Törlés", id=f"rule-del-{eid}", classes="rule-del-btn", variant="error")

        # Trigger row
        with Horizontal(classes="rule-row"):
            yield Label("HA:", classes="rule-row-label")
            yield Select(
                options=[(lbl, val) for lbl, val in self._trigger_options],
                id=f"rule-trigger-src-{eid}",
                allow_blank=True,
                prompt="– válassz triggert –",
                classes="rule-trigger-select",
            )
            yield Select(
                options=[(lbl, val) for lbl, val in _COMPARISON_OPS],
                id=f"rule-trigger-op-{eid}",
                value=">",
                allow_blank=False,
                classes="rule-op-select",
            )
            # Free numeric input (shown for sensor/counter triggers)
            yield Input(
                placeholder="érték (pl. 30)",
                id=f"rule-trigger-val-{eid}",
                classes="rule-val-input",
            )
            # Predefined dropdown (shown for discrete triggers: switch, relay state)
            yield Select(
                options=[("BE – 1", "1"), ("KI – 0", "0")],
                id=f"rule-trigger-val-sel-{eid}",
                value="1",
                allow_blank=False,
                classes="rule-val-select hidden",
            )

        # THEN action row
        with Horizontal(classes="rule-row"):
            yield Label("AKKOR:", classes="rule-row-label")
            yield Select(
                options=[(lbl, val) for lbl, val in self._action_options],
                id=f"rule-then-action-{eid}",
                allow_blank=True,
                prompt="– válassz akciót –",
                classes="rule-action-select",
            )
            yield Input(
                placeholder="érték",
                id=f"rule-then-value-{eid}",
                classes="rule-val-input",
            )

        # ELSE action row (hidden by default)
        with Horizontal(classes="rule-row", id=f"rule-else-row-{eid}"):
            yield Label("EGYÉBKÉNT:", classes="rule-row-label")
            yield Select(
                options=[(lbl, val) for lbl, val in self._action_options],
                id=f"rule-else-action-{eid}",
                allow_blank=True,
                prompt="– (elhagyható) –",
                classes="rule-action-select",
            )
            yield Input(
                placeholder="érték",
                id=f"rule-else-value-{eid}",
                classes="rule-val-input",
            )

        with Horizontal(classes="rule-card-footer"):
            yield Button(
                "± EGYÉBKÉNT ág hozzáadása",
                id=f"rule-toggle-else-{eid}",
                classes="rule-else-toggle-btn",
                variant="default",
            )

    def update_options(
        self,
        trigger_options: list[tuple[str, str]],
        action_options: list[tuple[str, str]],
    ) -> None:
        self._trigger_options = trigger_options
        self._action_options = action_options
        eid = self.entry_id
        try:
            self.query_one(f"#rule-trigger-src-{eid}", Select).set_options(
                [(lbl, val) for lbl, val in trigger_options]
            )
            for suffix in ("then", "else"):
                self.query_one(f"#rule-{suffix}-action-{eid}", Select).set_options(
                    [(lbl, val) for lbl, val in action_options]
                )
        except Exception:
            pass

    def get_entry(self) -> Optional[RuleEntry]:
        """Collect current widget values into a RuleEntry."""
        eid = self.entry_id
        try:
            src_sel     = self.query_one(f"#rule-trigger-src-{eid}", Select)
            op_sel      = self.query_one(f"#rule-trigger-op-{eid}", Select)
            val_inp     = self.query_one(f"#rule-trigger-val-{eid}", Input)
            val_sel     = self.query_one(f"#rule-trigger-val-sel-{eid}", Select)
            t_act       = self.query_one(f"#rule-then-action-{eid}", Select)
            t_val       = self.query_one(f"#rule-then-value-{eid}", Input).value.strip()
            e_act       = self.query_one(f"#rule-else-action-{eid}", Select)
            e_val       = self.query_one(f"#rule-else-value-{eid}", Input).value.strip()

            trigger_src = src_sel.value if isinstance(src_sel.value, str) else ""
            operator    = op_sel.value if isinstance(op_sel.value, str) else ">"
            then_raw    = t_act.value if isinstance(t_act.value, str) else ""
            else_raw    = e_act.value if isinstance(e_act.value, str) else ""

            # Use dropdown value if discrete selector is visible
            if val_sel.has_class("hidden"):
                tval = val_inp.value.strip()
            else:
                tval = str(val_sel.value) if isinstance(val_sel.value, str) else "1"

            then_cmd = _resolve_action(then_raw, t_val)
            else_cmd = _resolve_action(else_raw, e_val)

            return RuleEntry(
                entry_id=eid,
                trigger_source=trigger_src,
                has_value=_trigger_needs_value(trigger_src),
                operator=operator,
                trigger_value=tval,
                then_action=then_cmd,
                else_action=else_cmd,
            )
        except Exception:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        eid = self.entry_id
        if bid == f"rule-toggle-else-{eid}":
            event.stop()
            else_row = self.query_one(f"#rule-else-row-{eid}")
            else_row.toggle_class("hidden")
            btn: Button = event.button
            if else_row.has_class("hidden"):
                btn.label = "± EGYÉBKÉNT ág hozzáadása"
                btn.variant = "default"
            else:
                btn.label = "− EGYÉBKÉNT ág eltávolítása"
                btn.variant = "warning"

    def on_select_changed(self, event: Select.Changed) -> None:
        """Show/hide value input based on trigger type."""
        eid = self.entry_id
        sid = event.select.id or ""
        if sid != f"rule-trigger-src-{eid}":
            return
        src = event.value if isinstance(event.value, str) else ""
        needs_val = _trigger_needs_value(src)
        preset_opts = _get_trigger_value_options(src)
        try:
            op_sel   = self.query_one(f"#rule-trigger-op-{eid}", Select)
            val_inp  = self.query_one(f"#rule-trigger-val-{eid}", Input)
            val_sel  = self.query_one(f"#rule-trigger-val-sel-{eid}", Select)

            if not needs_val:
                # Event-only trigger (System#Boot, Timer, …) – hide both
                op_sel.add_class("hidden")
                val_inp.add_class("hidden")
                val_sel.add_class("hidden")
            elif preset_opts is not None:
                # Discrete value trigger (Switch, Power) – show dropdown, hide input
                op_sel.remove_class("hidden")
                val_inp.add_class("hidden")
                val_sel.remove_class("hidden")
                val_sel.set_options([(lbl, v) for lbl, v in preset_opts])
                # Default to "=" operator for state comparisons
                op_sel.value = "="
            else:
                # Numeric/free trigger (sensor, counter) – show input, hide dropdown
                op_sel.remove_class("hidden")
                val_inp.remove_class("hidden")
                val_sel.add_class("hidden")
                op_sel.value = ">"
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Action resolver
# ---------------------------------------------------------------------------

def _resolve_action(raw: str, value: str) -> str:
    """Convert internal action token + value to Tasmota command string."""
    if not raw:
        return ""
    if raw.startswith("__DIMMER_"):
        try:
            pct = max(0, min(100, int(value)))
        except ValueError:
            pct = 0
        return f"Dimmer {pct}"
    if raw.startswith("__PWM_"):
        n = raw.split("_")[-1]
        try:
            v = max(0, min(1023, int(value)))
        except ValueError:
            v = 0
        return f"PWM{n} {v}"
    if raw == "__DELAY":
        try:
            cs = max(1, int(value))
        except ValueError:
            cs = 10
        return f"Delay {cs}"
    if raw == "__TIMER":
        try:
            secs = max(1, int(value))
        except ValueError:
            secs = 60
        return f"RuleTimer1 {secs}"
    if raw == "__PUBLISH":
        return f"Publish {value}" if value else "Publish stat/topic/RESULT 1"
    # Plain command (Power1 ON, etc.)
    return raw


# ---------------------------------------------------------------------------
# Rule string generator
# ---------------------------------------------------------------------------

def generate_rule_commands(rule_num: int, entries: list[RuleEntry]) -> list[str]:
    """Convert list of RuleEntry into Tasmota Rule commands.

    Returns a list of strings to send sequentially, e.g.:
        ["Rule1 0", "Rule1 ON DS18B20#Temperature>30 DO Dimmer 80 ENDON", "Rule1 1"]
    """
    if not entries:
        return [f"Rule{rule_num} 0"]

    parts: list[str] = []
    for entry in entries:
        if not entry.trigger_source or not entry.then_action:
            continue

        trigger = entry.trigger_source
        if entry.has_value and entry.trigger_value:
            trigger_full = f"{trigger}{entry.operator}{entry.trigger_value}"
        else:
            trigger_full = trigger

        if entry.else_action:
            # IF / ELSE form
            if entry.has_value and entry.trigger_value:
                condition = f"({trigger}{entry.operator}{entry.trigger_value})"
            else:
                condition = f"({trigger}=1)"
            do_block = (
                f"IF {condition} {entry.then_action} "
                f"ELSE {entry.else_action} ENDIF"
            )
        else:
            do_block = entry.then_action

        parts.append(f"ON {trigger_full} DO {do_block} ENDON")

    if not parts:
        return [f"Rule{rule_num} 0"]

    rule_body = " ".join(parts)
    return [
        f"Rule{rule_num} 0",               # clear existing
        f"Rule{rule_num} {rule_body}",      # set new
        f"Rule{rule_num} 1",               # enable
    ]


# ---------------------------------------------------------------------------
# Main Rules Tab
# ---------------------------------------------------------------------------

class RulesTab(TabPane):
    """Visual Tasmota Rule builder tab."""

    DEFAULT_CSS = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._next_id = 1
        self._cards: list[RuleCard] = []
        self._trigger_options: list[tuple[str, str]] = list(_FIXED_TRIGGERS)
        self._action_options: list[tuple[str, str]] = [
            ("Késleltetés (Delay)", "__DELAY"),
            ("Timer indítása",      "__TIMER"),
            ("MQTT Publish",        "__PUBLISH"),
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="rules-tab"):
            # --- Top control row -------------------------------------------
            with Horizontal(id="rules-control-row"):
                yield Label("Rule:", classes="cfg-row-label")
                yield Select(
                    options=[
                        ("Rule 1", "1"), ("Rule 2", "2"), ("Rule 3", "3"),
                        ("Rule 4", "4"), ("Rule 5", "5"),
                    ],
                    id="rules-rule-select",
                    value="1",
                    allow_blank=False,
                )
                yield Button("+ Szabály hozzáadása",  id="rules-add-btn",        variant="success")
                yield Button("🗑 Mind törlése",        id="rules-clear-btn",       variant="error")
                yield Button("⚙ GPIO frissítés",      id="rules-refresh-gpio-btn", variant="default")
                yield Button("🔄 Lekérdezés eszközről", id="rules-fetch-btn",     variant="default")

            # --- Info hint when no GPIO configured -------------------------
            yield Label(
                "ℹ Trigger és akció opciók a Config / Board lap GPIO kiosztásából töltődnek be.",
                id="rules-gpio-hint",
                classes="hint",
            )

            # --- Card container --------------------------------------------
            with ScrollableContainer(id="rules-cards-container"):
                yield Label(
                    "Adj hozzá szabályokat a [bold]+ Szabály hozzáadása[/bold] gombbal.",
                    id="rules-empty-hint",
                    classes="hint",
                )

            # --- Preview ---------------------------------------------------
            with Vertical(id="rules-preview-panel"):
                yield Static("Generált Tasmota parancsok", classes="section-title")
                yield TextArea(
                    "",
                    id="rules-preview-area",
                    read_only=True,
                    show_line_numbers=False,
                    classes="rules-preview-textarea",
                )

            # --- Send row --------------------------------------------------
            with Horizontal(id="rules-send-row"):
                yield Button("📡 Küldés soros porton", id="rules-send-serial-btn", variant="primary")
                yield Label("", id="rules-send-status", classes="hint")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh_preview)

    # ------------------------------------------------------------------
    # Public: called by app when tab is activated
    # ------------------------------------------------------------------

    def update_from_gpio(self, assignments: dict[int, str]) -> None:
        """Refresh trigger/action options based on current GPIO config."""
        self._trigger_options = _triggers_from_assignments(assignments)
        self._action_options  = _actions_from_assignments(assignments)
        for card in self._cards:
            card.update_options(self._trigger_options, self._action_options)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "rules-add-btn":
            self._add_card()
        elif bid == "rules-clear-btn":
            self._clear_all_cards()
        elif bid == "rules-refresh-gpio-btn":
            self._refresh_gpio_from_app()
        elif bid == "rules-fetch-btn":
            self.run_worker(self._fetch_rules(), name="rules_fetch")
        elif bid == "rules-send-serial-btn":
            self.run_worker(self._send_rules(), name="rules_send")
        elif bid.startswith("rule-del-"):
            try:
                eid = int(bid.split("-")[-1])
                self._remove_card(eid)
            except ValueError:
                pass

    def _refresh_gpio_from_app(self) -> None:
        """Re-read GPIO assignments from Board/Config tab and update options."""
        gpio: dict = {}
        try:
            from tasmota_manager.screens.board_screen import BoardTab
            board_tab = self.app.query_one(BoardTab)  # type: ignore[attr-defined]
            gpio = {k: v for k, v in board_tab._gpio_assignments.items() if v and v != "none"}
        except Exception:
            pass
        if not gpio:
            try:
                from tasmota_manager.screens.config_screen import ConfigTab
                cfg_tab = self.app.query_one(ConfigTab)  # type: ignore[attr-defined]
                gpio = cfg_tab._get_gpio_assignments()
            except Exception:
                pass
        self.update_from_gpio(gpio)
        if gpio:
            self.notify(
                f"{len(gpio)} GPIO kiosztás betöltve (trigger/akció opciók frissítve).",
                severity="information",
            )
        else:
            self.notify(
                "Nincs GPIO kiosztás. Állítsd be a Config lapon, vagy töltsd le az eszközről.",
                severity="warning",
            )

    # ------------------------------------------------------------------
    # Card management
    # ------------------------------------------------------------------

    def _add_card(self) -> None:
        eid = self._next_id
        self._next_id += 1
        card = RuleCard(eid, id=f"rule-card-{eid}", classes="rule-card")
        card.update_options(self._trigger_options, self._action_options)
        self._cards.append(card)
        container = self.query_one("#rules-cards-container")
        # Hide empty hint
        try:
            self.query_one("#rules-empty-hint").add_class("hidden")
        except Exception:
            pass
        container.mount(card)

    def _remove_card(self, entry_id: int) -> None:
        self._cards = [c for c in self._cards if c.entry_id != entry_id]
        try:
            self.query_one(f"#rule-card-{entry_id}").remove()
        except Exception:
            pass
        if not self._cards:
            try:
                self.query_one("#rules-empty-hint").remove_class("hidden")
            except Exception:
                pass
        self._refresh_preview()

    def _clear_all_cards(self) -> None:
        for card in list(self._cards):
            try:
                self.query_one(f"#rule-card-{card.entry_id}").remove()
            except Exception:
                pass
        self._cards = []
        try:
            self.query_one("#rules-empty-hint").remove_class("hidden")
        except Exception:
            pass
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _get_rule_num(self) -> int:
        try:
            v = self.query_one("#rules-rule-select", Select).value
            return int(v) if isinstance(v, str) else 1
        except Exception:
            return 1

    def _collect_entries(self) -> list[RuleEntry]:
        entries = []
        for card in self._cards:
            entry = card.get_entry()
            if entry:
                entries.append(entry)
        return entries

    def _refresh_preview(self) -> None:
        try:
            rule_num = self._get_rule_num()
            entries  = self._collect_entries()
            cmds     = generate_rule_commands(rule_num, entries)
            preview  = self.query_one("#rules-preview-area", TextArea)
            preview.load_text("\n".join(cmds))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Send to device
    # ------------------------------------------------------------------

    async def _send_rules(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#rules-send-status")
        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat! (Serial tab → Csatlakozás)", severity="warning")
            return

        rule_num = self._get_rule_num()
        entries  = self._collect_entries()
        cmds     = generate_rule_commands(rule_num, entries)

        status_lbl.update("[yellow]Küldés…[/yellow]")
        try:
            for cmd in cmds:
                serial_bridge.send(cmd)
                await asyncio.sleep(0.3)
            status_lbl.update(f"[green]● {len(cmds)} parancs elküldve[/green]")
            self.notify(f"Rule{rule_num} elküldve ({len(cmds)} parancs)", severity="information")
        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")

    # ------------------------------------------------------------------
    # Fetch from device
    # ------------------------------------------------------------------

    async def _fetch_rules(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        status_lbl: Label = self.query_one("#rules-send-status")
        if not serial_bridge.is_connected:
            self.notify("Nincs soros port kapcsolat! (Serial tab → Csatlakozás)", severity="warning")
            return

        rule_num = self._get_rule_num()
        status_lbl.update("[yellow]Lekérés…[/yellow]")
        try:
            serial_bridge.clear_buffer()
            serial_bridge.send(f"Rule{rule_num}")
            await asyncio.sleep(1.0)
            lines = list(serial_bridge.line_buffer)
            raw = _parse_rule_response(lines, rule_num)
            if raw:
                preview = self.query_one("#rules-preview-area", TextArea)
                preview.load_text(f"# Eszközről lekérdezett Rule{rule_num}:\n{raw}")
                status_lbl.update("[green]● Lekérdezve[/green]")
                self.notify(f"Rule{rule_num} lekérdezve – a nyers szöveg az előnézetben látható.", severity="information")
            else:
                status_lbl.update("[dim]Nincs adat[/dim]")
                self.notify(f"Rule{rule_num} üres vagy nem érkezett válasz.", severity="warning")
        except Exception as exc:
            status_lbl.update(f"[red]Hiba: {exc}[/red]")


# ---------------------------------------------------------------------------
# Rule response parser
# ---------------------------------------------------------------------------

def _parse_rule_response(lines: list[str], rule_num: int) -> str:
    """Extract raw Rule string from device response lines."""
    key = f'"Rules"'
    for line in lines:
        if key not in line:
            continue
        # Try to find the Rules value in JSON
        try:
            import json
            start = line.find("{")
            if start < 0:
                continue
            data = json.loads(line[start:line.rfind("}") + 1])
            rules_val = data.get("Rules") or data.get(f"Rule{rule_num}", {}).get("Rules", "")
            if rules_val:
                return str(rules_val)
        except Exception:
            pass
        # Fallback: return the raw line
        return line.strip()
    return ""
