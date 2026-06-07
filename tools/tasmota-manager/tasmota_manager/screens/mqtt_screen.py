"""MQTT Monitor tab – live broker monitoring with topic tree and payload viewer."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabPane,
    TextArea,
    Tree,
)
from textual.widgets.tree import TreeNode

from tasmota_manager.mqtt_client import MqttMessage
from tasmota_manager.groups_manager import (
    list_users,
    list_regions,
    get_devices_for_region,
)


_PREFIX_COLORS = {
    "tele": "bright_cyan",
    "stat": "bright_green",
    "cmnd": "yellow",
}

_MAX_LOG_LINES = 500


class MQTTTab(TabPane):
    """Real-time MQTT broker monitor."""

    connected: reactive[bool] = reactive(False)
    message_count: reactive[int] = reactive(0)

    # topic tree structure: {prefix: {device: {command: last_ts}}}
    _topic_tree_data: dict[str, dict[str, dict[str, str]]] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="mqtt-tab"):
            # --- Connection: inputs row + buttons row (always visible) ---
            with Vertical(id="mqtt-connect-row"):
                with Horizontal(id="mqtt-connect-fields"):
                    yield Label("Host:", classes="label")
                    yield Input(value="broker.emqx.io", id="mqtt-host-input")
                    yield Label("Port:", classes="label")
                    yield Input(value="1883", id="mqtt-port-input")
                    yield Label("Topic:", classes="label")
                    yield Input(value="#", id="mqtt-sub-topic-input")
                with Horizontal(id="mqtt-connect-actions"):
                    yield Button("Csatlakozás", id="mqtt-connect-btn", variant="success")
                    yield Label("", id="mqtt-conn-status")

            # --- Main split: tree + right panel -------------------------
            with Horizontal(id="mqtt-main"):
                # Left: topic tree
                with Vertical(id="mqtt-tree-panel"):
                    yield Static("Topic fa", classes="section-title")
                    yield Tree("Topics", id="mqtt-tree")

                # Right: payload viewer + log
                with Vertical(id="mqtt-right-panel"):
                    with Vertical(id="mqtt-payload-panel"):
                        yield Static("Legutóbbi üzenet", classes="section-title")
                        yield Label("", id="mqtt-payload-topic-label")
                        yield TextArea(
                            "",
                            id="mqtt-payload-area",
                            read_only=True,
                            language="json",
                        )

                    yield RichLog(
                        id="mqtt-log-panel",
                        markup=True,
                        auto_scroll=True,
                    )

            # --- Device selector row ------------------------------------
            with Horizontal(id="mqtt-device-selector-row"):
                yield Label("Eszköz:", classes="label")
                yield Select(
                    options=[],
                    id="mqtt-sel-user",
                    allow_blank=True,
                    prompt="– User –",
                )
                yield Select(
                    options=[],
                    id="mqtt-sel-region",
                    allow_blank=True,
                    prompt="– Régió –",
                )
                yield Select(
                    options=[],
                    id="mqtt-sel-device",
                    allow_blank=True,
                    prompt="– Eszköz –",
                )
                yield Button("Monitorozás", id="mqtt-monitor-device-btn", variant="primary")

            # --- Filter row ---------------------------------------------
            with Horizontal(id="mqtt-filter-row"):
                yield Label("Szűrő:", classes="label")
                yield Select(
                    options=[
                        ("Összes", "all"),
                        ("tele/", "tele"),
                        ("stat/", "stat"),
                        ("cmnd/", "cmnd"),
                    ],
                    value="all",
                    id="mqtt-prefix-filter",
                    allow_blank=False,
                )
                yield Input(placeholder="Eszköz topic (pl. A1B2C3)", id="mqtt-device-filter")
                yield Label("Üzenetek: 0", id="mqtt-count-label")
                yield Button("Törlés", id="mqtt-clear-btn", variant="default")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.run_worker(self._mqtt_consumer(), exclusive=True, name="mqtt_consumer")
        self._refresh_user_selector()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "mqtt-connect-btn":
            self._toggle_connection()
        elif bid == "mqtt-clear-btn":
            log: RichLog = self.query_one("#mqtt-log-panel")
            log.clear()
            self.message_count = 0
            self._update_count()
        elif bid == "mqtt-monitor-device-btn":
            self._start_monitoring_selected_device()

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.select.id
        if sid == "mqtt-sel-user":
            user_id = event.value
            if user_id and user_id is not Select.BLANK and isinstance(user_id, str):
                regions = [(name, rid) for rid, name in list_regions(user_id)]
            else:
                regions = []
            self.query_one("#mqtt-sel-region", Select).set_options(regions)
            self.query_one("#mqtt-sel-device", Select).set_options([])
        elif sid == "mqtt-sel-region":
            region_id = event.value
            user_sel = self.query_one("#mqtt-sel-user", Select)
            user_id = user_sel.value
            if (region_id and region_id is not Select.BLANK and isinstance(region_id, str)
                    and user_id and isinstance(user_id, str)):
                devices_data = get_devices_for_region(user_id, region_id)
                device_opts = [(d["device_id"], d["device_id"]) for d in devices_data]
            else:
                device_opts = []
            self.query_one("#mqtt-sel-device", Select).set_options(device_opts)

    def _refresh_user_selector(self) -> None:
        """Populate the user dropdown from groups.json."""
        try:
            users = [(name, uid) for uid, name in list_users()]
            self.query_one("#mqtt-sel-user", Select).set_options(users)
        except Exception:
            pass

    def _start_monitoring_selected_device(self) -> None:
        """Subscribe to the selected device's MQTT topic and update the filter."""
        user_id = self.query_one("#mqtt-sel-user", Select).value
        region_id = self.query_one("#mqtt-sel-region", Select).value
        device_id = self.query_one("#mqtt-sel-device", Select).value
        if (not user_id or user_id is Select.BLANK
                or not region_id or region_id is Select.BLANK
                or not device_id or device_id is Select.BLANK):
            self.notify("Válassz user-t, régiót és eszközt!", severity="warning")
            return

        from tasmota_manager.groups_manager import build_mqtt_subscribe_topic
        sub_topic = build_mqtt_subscribe_topic(str(region_id), str(user_id), str(device_id))
        # Update the subscription topic and device filter
        self.query_one("#mqtt-sub-topic-input", Input).value = sub_topic
        self.query_one("#mqtt-device-filter", Input).value = str(device_id)

        # Push user/region/device_id to Board tab
        try:
            self.app.set_monitored_device(  # type: ignore[attr-defined]
                user_id=str(user_id),
                region_id=str(region_id),
                device_id=str(device_id),
            )
        except Exception:
            pass

        # Reconnect MQTT with new topic if already connected
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        if mqtt_mgr.connected:
            host = self.query_one("#mqtt-host-input", Input).value.strip()
            port_str = self.query_one("#mqtt-port-input", Input).value.strip()
            port = int(port_str) if port_str.isdigit() else 1883
            try:
                mqtt_user = self.app.query_one("#cfg-mqtt-user", Input).value.strip()  # type: ignore[attr-defined]
                mqtt_pass = self.app.query_one("#cfg-mqtt-pass", Input).value.strip()  # type: ignore[attr-defined]
            except Exception:
                mqtt_user = mqtt_pass = ""
            mqtt_mgr.disconnect()
            mqtt_mgr.connect(
                host=host, port=port,
                user=mqtt_user or "",
                password=mqtt_pass or "",
                subscribe_topic=sub_topic,
            )
            self.notify(
                f"Monitorozás: {user_id}/{region_id}/{device_id}",
                severity="information",
            )
        else:
            self.notify(
                f"Eszköz kiválasztva: {user_id}/{region_id}/{device_id} — kattints Csatlakozás-ra!",
                severity="information",
            )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data and isinstance(node.data, str):
            topic = node.data
            mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
            msg = mqtt_mgr.last_messages.get(topic)
            if msg:
                self._show_payload(msg)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _toggle_connection(self) -> None:
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        btn: Button = self.query_one("#mqtt-connect-btn")
        lbl: Label = self.query_one("#mqtt-conn-status")

        if mqtt_mgr.connected:
            mqtt_mgr.disconnect()
            self.connected = False
            btn.label = "Csatlakozás"
            btn.variant = "success"
            lbl.update("Lecsatlakozva")
        else:
            host = self.query_one("#mqtt-host-input", Input).value.strip()
            port_str = self.query_one("#mqtt-port-input", Input).value.strip()
            sub_topic = self.query_one("#mqtt-sub-topic-input", Input).value.strip() or "#"
            port = int(port_str) if port_str.isdigit() else 1883

            # Read credentials from Config tab (not exposed in Monitor UI)
            mqtt_user = ""
            mqtt_pass = ""
            try:
                mqtt_user = self.app.query_one("#cfg-mqtt-user", Input).value.strip()  # type: ignore[attr-defined]
                mqtt_pass = self.app.query_one("#cfg-mqtt-pass", Input).value.strip()  # type: ignore[attr-defined]
            except Exception:
                pass

            try:
                mqtt_mgr.connect(
                    host=host, port=port,
                    user=mqtt_user or "",
                    password=mqtt_pass or "",
                    subscribe_topic=sub_topic,
                )
                self.connected = True
                btn.label = "Lecsatlakozás"
                btn.variant = "error"
                lbl.update(f"[green]● {host}:{port}[/green]")
            except Exception as exc:
                lbl.update(f"[red]Hiba: {exc}[/red]")

    # ------------------------------------------------------------------
    # Background MQTT consumer
    # ------------------------------------------------------------------

    async def _mqtt_consumer(self) -> None:
        mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
        while True:
            try:
                msg: MqttMessage = await asyncio.wait_for(
                    mqtt_mgr.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.5)
                continue

            self._handle_message(msg)

    def _handle_message(self, msg: MqttMessage) -> None:
        # Apply filters
        prefix_filter = self.query_one("#mqtt-prefix-filter", Select).value
        device_filter = self.query_one("#mqtt-device-filter", Input).value.strip().lower()

        if prefix_filter != "all" and msg.prefix != prefix_filter:
            return
        if device_filter and device_filter not in msg.device_topic.lower():
            return

        self.message_count += 1
        self._update_count()
        self._update_topic_tree(msg)
        self._log_message(msg)

    def _update_topic_tree(self, msg: MqttMessage) -> None:
        tree: Tree = self.query_one("#mqtt-tree")
        prefix  = msg.prefix
        device  = msg.device_topic
        command = msg.command
        if not prefix or not device:
            return

        ts = msg.timestamp.strftime("%H:%M:%S")

        # Build/update nested structure: {prefix: {device: {command: ts}}}
        if prefix not in self._topic_tree_data:
            self._topic_tree_data[prefix] = {}
        if device not in self._topic_tree_data[prefix]:
            self._topic_tree_data[prefix][device] = {}
        self._topic_tree_data[prefix][device][command] = ts

        # Rebuild tree display
        tree.clear()
        for pfx, devices in sorted(self._topic_tree_data.items()):
            color = _PREFIX_COLORS.get(pfx, "white")
            pfx_node = tree.root.add(f"[{color}]{pfx}[/{color}]", expand=True)
            for dev, commands in sorted(devices.items()):
                mqtt_mgr = self.app.mqtt_manager  # type: ignore[attr-defined]
                online = mqtt_mgr.is_device_online(dev)
                if online is True:
                    dot = "[green]●[/green]"
                elif online is False:
                    dot = "[red]●[/red]"
                else:
                    dot = "[dim]●[/dim]"
                dev_node = pfx_node.add(f"{dot} {dev}", expand=True)
                for cmd, last_ts in sorted(commands.items()):
                    dev_node.add_leaf(
                        f"[dim]{cmd}[/dim]  [dim]{last_ts}[/dim]",
                        data=msg.topic,
                    )

    def _log_message(self, msg: MqttMessage) -> None:
        log: RichLog = self.query_one("#mqtt-log-panel")
        color = _PREFIX_COLORS.get(msg.prefix, "white")
        ts = msg.timestamp.strftime("%H:%M:%S")

        # Truncate long payloads in log
        payload_display = msg.payload_raw
        if len(payload_display) > 120:
            payload_display = payload_display[:117] + "…"

        log.write(
            f"[dim]{ts}[/dim]  [{color}]{msg.topic}[/{color}]  "
            f"[dim white]{payload_display}[/dim white]"
        )

        # Show in payload viewer if it's the most recently selected topic
        self._show_payload(msg)

    def _show_payload(self, msg: MqttMessage) -> None:
        lbl: Label = self.query_one("#mqtt-payload-topic-label")
        area: TextArea = self.query_one("#mqtt-payload-area")
        lbl.update(
            f"[bold]{msg.topic}[/bold]  [dim]{msg.timestamp.strftime('%H:%M:%S')}[/dim]"
        )
        if isinstance(msg.payload_json, (dict, list)):
            pretty = json.dumps(msg.payload_json, indent=2, ensure_ascii=False)
        else:
            pretty = str(msg.payload_raw)
        area.load_text(pretty)

    def _update_count(self) -> None:
        lbl: Label = self.query_one("#mqtt-count-label")
        lbl.update(f"Üzenetek: {self.message_count}")
