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


@dataclass
class MqttMessage:
    topic: str
    payload_raw: str
    payload_json: object        # parsed JSON or raw string
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def prefix(self) -> str:
        return self.topic.split("/")[0] if "/" in self.topic else ""

    @property
    def device_topic(self) -> str:
        parts = self.topic.split("/")
        return parts[1] if len(parts) > 1 else ""

    @property
    def command(self) -> str:
        parts = self.topic.split("/")
        return parts[2] if len(parts) > 2 else ""


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
            for topic in self.last_messages:
                parts = topic.split("/")
                if len(parts) >= 2:
                    devices.add(parts[1])
            return sorted(devices)
