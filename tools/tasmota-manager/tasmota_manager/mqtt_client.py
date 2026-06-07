"""paho-mqtt based MQTT client with asyncio queue delivery."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import paho.mqtt.client as mqtt


_KNOWN_PREFIXES = frozenset({"tele", "stat", "cmnd"})


@dataclass
class MqttMessage:
    """Single received MQTT message.

    Supports both legacy flat topics (tele/DEVICE/CMD) and grouped topics
    (user/region/DEVICE/tele/CMD) produced by Tasmota when a custom FullTopic
    containing user/region segments is configured.
    """

    topic: str
    payload_raw: str
    payload_json: object        # parsed JSON or raw string
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def _is_grouped(self) -> bool:
        """Return True for user/region/device/prefix/cmd shaped topics."""
        parts = self.topic.split("/")
        return (
            len(parts) >= 4
            and bool(parts[0])
            and parts[0].lower() not in _KNOWN_PREFIXES
        )

    @property
    def prefix(self) -> str:
        """MQTT prefix: tele / stat / cmnd."""
        parts = self.topic.split("/")
        if self._is_grouped:
            return parts[3] if len(parts) > 3 else ""
        return parts[0] if parts else ""

    @property
    def device_topic(self) -> str:
        """Device identifier (the Tasmota Topic value)."""
        parts = self.topic.split("/")
        if self._is_grouped:
            return parts[2] if len(parts) > 2 else ""
        return parts[1] if len(parts) > 1 else ""

    @property
    def command(self) -> str:
        """Command / sensor name (last path segment(s))."""
        parts = self.topic.split("/")
        if self._is_grouped:
            return "/".join(parts[4:]) if len(parts) > 4 else ""
        return "/".join(parts[2:]) if len(parts) > 2 else ""

    @property
    def user_id(self) -> str:
        """User segment for grouped topics; empty string for legacy format."""
        parts = self.topic.split("/")
        return parts[0] if self._is_grouped else ""

    @property
    def region_id(self) -> str:
        """Region segment for grouped topics; empty string for legacy format."""
        parts = self.topic.split("/")
        return parts[1] if self._is_grouped and len(parts) > 1 else ""


@dataclass
class DeviceOnlineStatus:
    topic: str
    online: bool
    last_seen: datetime = field(default_factory=datetime.now)


class MQTTManager:
    """
    Thread-safe MQTT client that pushes received messages into an asyncio queue.
    """

    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.queue: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.connected = False
        self._subscribe_topic = "#"
        self._host = ""
        self._port = 1883
        # device_topic → online status
        self.device_status: dict[str, DeviceOnlineStatus] = {}
        # topic → last MqttMessage
        self.last_messages: dict[str, MqttMessage] = {}
        self.on_connect_cb: Optional[Callable[[bool], None]] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        host: str,
        port: int = 1883,
        user: str = "",
        password: str = "",
        subscribe_topic: str = "#",
    ) -> None:
        self.disconnect()
        self._loop = asyncio.get_event_loop()
        self._host = host
        self._port = port
        self._subscribe_topic = subscribe_topic

        self._client = mqtt.Client(client_id="tasmota_manager", clean_session=True)
        if user:
            self._client.username_pw_set(user, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._client.connect_async(host, port, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self.connected = False

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        if self._client and self.connected:
            self._client.publish(topic, payload, qos=qos)

    # ------------------------------------------------------------------
    # paho callbacks (called from paho thread)
    # ------------------------------------------------------------------

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        if rc == 0:
            self.connected = True
            client.subscribe(self._subscribe_topic)
            if self.on_connect_cb:
                self.on_connect_cb(True)
        else:
            self.connected = False
            if self.on_connect_cb:
                self.on_connect_cb(False)

    def _on_disconnect(self, client, userdata, rc: int) -> None:
        self.connected = False

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload_raw = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            payload_raw = str(msg.payload)

        try:
            payload_json = json.loads(payload_raw)
        except (json.JSONDecodeError, ValueError):
            payload_json = payload_raw

        message = MqttMessage(
            topic=msg.topic,
            payload_raw=payload_raw,
            payload_json=payload_json,
        )

        # Track LWT online status
        if message.command == "LWT":
            with self._lock:
                self.device_status[message.device_topic] = DeviceOnlineStatus(
                    topic=message.device_topic,
                    online=(payload_raw.strip().lower() == "online"),
                )

        with self._lock:
            self.last_messages[msg.topic] = message

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self.queue.put_nowait, message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_device_online(self, device_topic: str) -> Optional[bool]:
        with self._lock:
            status = self.device_status.get(device_topic)
            return status.online if status else None

    def get_known_devices(self) -> list[str]:
        with self._lock:
            devices: set[str] = set()
            for msg in self.last_messages.values():
                dt = msg.device_topic
                if dt:
                    devices.add(dt)
            return sorted(devices)
