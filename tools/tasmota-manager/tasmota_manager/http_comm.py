"""HTTP API bridge for Tasmota devices.

Provides the same interface as AsyncSerialBridge so the rest of the app
can use either serial or HTTP without knowing the difference.

Tasmota HTTP API endpoint:
    GET http://<ip>/cm?cmnd=<command>[&user=admin&password=<pw>]

Every response is also injected into `line_buffer` and the asyncio queues
in the same MQT-prefixed format that the serial bridge produces, so all
existing parsers (board_screen, config_screen, rules_screen) work without
modification:
    "MQT: <ip>/stat/RESULT = <json>"
"""
from __future__ import annotations

import asyncio
import collections
import json as _json
import threading
from typing import Optional
from urllib.parse import quote

import requests


_CONNECT_TIMEOUT = 5   # seconds
_SEND_TIMEOUT    = 8   # seconds

_DEFAULT_LOG_DIR = None   # HTTP responses are not logged to file (serial has its own log)


class TasmotaHttpBridge:
    """HTTP-based Tasmota command bridge.

    Compatible interface with AsyncSerialBridge:
      - .is_connected   (property)
      - .send(cmd)
      - .clear_buffer()
      - .line_buffer    (deque)
      - .queue          (asyncio.Queue – same lines as line_buffer)
      - .state_queue    (asyncio.Queue – same lines, for board tab)
    """

    BUFFER_SIZE = 500

    def __init__(self) -> None:
        self._ip: str = ""
        self._password: str = ""
        self._is_connected: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.line_buffer: collections.deque[str] = collections.deque(
            maxlen=self.BUFFER_SIZE
        )
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.state_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        # Not used for HTTP, kept for interface compatibility
        self.detected_chip: Optional[str] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, ip: str, password: str = "") -> bool:
        """Try to connect to a Tasmota device at the given IP.

        Sends 'Status 2' to verify the device is reachable and responding.
        Returns True on success, False on failure.
        """
        ip = ip.strip().rstrip("/")
        if not ip.startswith("http"):
            ip = f"http://{ip}"
        self._ip = ip
        self._password = password.strip()
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None

        try:
            resp = self._get("Status 2", timeout=_CONNECT_TIMEOUT)
            if resp is not None:
                self._is_connected = True
                return True
        except Exception:
            pass
        self._is_connected = False
        return False

    def disconnect(self) -> None:
        self._is_connected = False
        self._ip = ""
        self._password = ""

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def ip(self) -> str:
        """Current device IP (with http:// prefix), or empty string."""
        return self._ip

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(self, command: str) -> Optional[dict]:
        """Send a Tasmota command via HTTP and return the JSON response.

        Also injects the response into line_buffer / queue / state_queue in
        MQT-format so existing parsers work without changes.
        Returns the parsed JSON dict, or None on error.
        """
        if not self._is_connected:
            return None
        command = command.strip()
        try:
            data = self._get(command, timeout=_SEND_TIMEOUT)
            if data is not None:
                # Inject into queues as a fake MQT line so parsers pick it up
                fake_line = self._make_mqt_line(command, data)
                self._enqueue(fake_line)
            return data
        except Exception:
            return None

    def clear_buffer(self) -> None:
        self.line_buffer.clear()

    # ------------------------------------------------------------------
    # Config backup / restore
    # ------------------------------------------------------------------

    def download_config(self) -> Optional[bytes]:
        """Download the full Tasmota config backup via GET /dl.

        Returns raw bytes of the .dmp binary file, or None on error.
        The /dl endpoint returns the binary config backup, not JSON.
        Authentication uses the same password as the command endpoint.
        """
        if not self._is_connected:
            return None
        try:
            url = f"{self._ip}/dl"
            params: dict = {}
            if self._password:
                params["user"] = "admin"
                params["password"] = self._password
            resp = requests.get(url, params=params, timeout=_SEND_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def upload_config(self, data: bytes) -> bool:
        """Restore a Tasmota config backup via POST /u2 (multipart upload).

        Tasmota expects a multipart/form-data POST with field name 'u2'.
        After a successful upload, the device reboots automatically.
        Returns True if the server responded with 200 OK.
        """
        if not self._is_connected:
            return False
        try:
            url = f"{self._ip}/u2"
            params: dict = {}
            if self._password:
                params["user"] = "admin"
                params["password"] = self._password
            files = {"u2": ("config.dmp", data, "application/octet-stream")}
            resp = requests.post(url, params=params, files=files, timeout=_SEND_TIMEOUT)
            resp.raise_for_status()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self, cmd: str) -> str:
        params = f"cmnd={quote(cmd)}"
        if self._password:
            params += f"&user=admin&password={quote(self._password)}"
        return f"{self._ip}/cm?{params}"

    def _get(self, cmd: str, timeout: int = _SEND_TIMEOUT) -> Optional[dict]:
        """Perform the HTTP GET and return parsed JSON, or None."""
        url = self._build_url(cmd)
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {}

    def _make_mqt_line(self, cmd: str, data: dict) -> str:
        """Build a fake MQT log line that mimics Tasmota serial output.

        Format:  MQT: <ip>/stat/RESULT = <json>
        Special cases map command → topic suffix:
          Status 0  → STATUS  (and also STATUS1..STATUS11 for sub-responses)
          Status N  → STATUS<N>
          GPIO      → RESULT
          Rule1     → RESULT
          Power*    → RESULT  and  POWER<n>
          etc.
        """
        topic = self._cmd_to_topic(cmd)
        ip_short = self._ip.replace("http://", "").replace("https://", "")
        json_str = _json.dumps(data)
        return f"MQT: {ip_short}/stat/{topic} = {json_str}"

    @staticmethod
    def _cmd_to_topic(cmd: str) -> str:
        """Map a Tasmota command to the MQT topic suffix it would publish to."""
        cmd_upper = cmd.strip().upper()
        if cmd_upper == "STATUS 0" or cmd_upper == "STATUS":
            return "STATUS"
        if cmd_upper.startswith("STATUS "):
            n = cmd_upper.split()[-1]
            return f"STATUS{n}"
        # Power1, Power2 …
        if cmd_upper.startswith("POWER"):
            return "RESULT"
        return "RESULT"

    def _enqueue(self, line: str) -> None:
        """Push a fake MQT line into all consumers (same as serial bridge)."""
        self.line_buffer.append(line)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self.queue.put_nowait, line)
            if self.state_queue.full():
                try:
                    self.state_queue.get_nowait()
                except Exception:
                    pass
            self._loop.call_soon_threadsafe(self.state_queue.put_nowait, line)
