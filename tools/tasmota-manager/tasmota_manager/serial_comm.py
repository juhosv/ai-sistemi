"""Async-friendly serial port communication layer."""
from __future__ import annotations

import asyncio
import collections
import threading
import time
from typing import Callable, Optional

import serial
import serial.tools.list_ports


class SerialComm:
    """
    Thread-based serial reader with asyncio callback delivery.

    Usage:
        comm = SerialComm()
        comm.connect("COM5", 115200)
        comm.on_line = lambda line: ...  # called in calling thread
        comm.send("Status")
        comm.disconnect()
    """

    def __init__(self) -> None:
        self._ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.port: Optional[str] = None
        self.baud: int = 115200
        # Callback: called from reader thread with each decoded line
        self.on_line: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, port: str, baud: int = 115200) -> None:
        if self._ser and self._ser.is_open:
            self.disconnect()
        self._ser = serial.Serial(port, baud, timeout=0.1)
        self.port = port
        self.baud = baud
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self.port = None

    @property
    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(self, command: str) -> None:
        """Send a single Tasmota console command (newline appended)."""
        if not self.is_connected:
            raise RuntimeError("Not connected to serial port")
        self._ser.write((command.strip() + "\n").encode("utf-8"))

    def send_config_block(
        self,
        commands: list[str],
        delay: float = 0.3,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Send a list of commands sequentially with a small inter-command delay."""
        total = len(commands)
        for i, cmd in enumerate(commands):
            self.send(cmd)
            if progress_cb:
                progress_cb(i + 1, total)
            time.sleep(delay)

    # ------------------------------------------------------------------
    # Reader thread
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        buf = b""
        while self._running:
            try:
                if self._ser and self._ser.in_waiting:
                    buf += self._ser.read(self._ser.in_waiting)
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if line and self.on_line:
                            self.on_line(line)
                else:
                    time.sleep(0.02)
            except (serial.SerialException, OSError):
                self._running = False
                if self.on_line:
                    self.on_line("[HIBA] Soros port kapcsolat megszakadt")
                break


class AsyncSerialBridge:
    """
    Wraps SerialComm and delivers lines to an asyncio queue,
    making it easy to consume in Textual workers.

    Also maintains a rolling line buffer so other modules can inspect
    recent output (e.g. to parse Status responses after a query).
    """

    BUFFER_SIZE = 500

    def __init__(self) -> None:
        self.comm = SerialComm()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        # Rolling buffer of recent lines (thread-safe deque)
        self.line_buffer: collections.deque[str] = collections.deque(
            maxlen=self.BUFFER_SIZE
        )
        # Detected chip family, updated by chip detection logic
        self.detected_chip: Optional[str] = None

    def connect(self, port: str, baud: int = 115200) -> None:
        self._loop = asyncio.get_event_loop()
        self.comm.on_line = self._enqueue
        self.comm.connect(port, baud)

    def disconnect(self) -> None:
        self.comm.disconnect()
        self.detected_chip = None

    def send(self, command: str) -> None:
        self.comm.send(command)

    def clear_buffer(self) -> None:
        self.line_buffer.clear()

    def _enqueue(self, line: str) -> None:
        self.line_buffer.append(line)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self.queue.put_nowait, line)

    @property
    def is_connected(self) -> bool:
        return self.comm.is_connected

    @property
    def port(self) -> Optional[str]:
        return self.comm.port
