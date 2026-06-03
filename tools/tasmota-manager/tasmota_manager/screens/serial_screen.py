"""Serial Monitor tab – real-time serial port monitor."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, RichLog, Select, Static, TabPane

from tasmota_manager.utils import list_serial_ports, rssi_to_bars, rssi_label

BAUD_RATES = [9600, 19200, 38400, 57600, 74880, 115200, 230400, 460800, 921600]

# Gyors parancsok: (gomb szöveg, Tasmota parancs, tooltip)
QUICK_COMMANDS = [
    ("WiFi info",    "Status 5",  "IP, MAC, SSID, RSSI"),
    ("GPIO állapot", "Status 11", "GPIO kiosztás és állapot"),
    ("Eszköz info",  "Status",    "Általános státusz"),
    ("Sensor",       "Status 10", "Szenzor értékek"),
    ("Uptime",       "Uptime",    "Üzemidő"),
    ("Restart",      "Restart 1", "Újraindítás"),
]

# Tasmota log prefix → Rich color
_PREFIX_COLORS: dict[str, str] = {
    "RST": "bold orange3",
    "CFG": "dim white",
    "WIF": "cyan",
    "MQT": "bright_cyan",
    "APP": "bright_white",
    "ERR": "bold red",
    "SRC": "green",
    "CMD": "yellow",
    "LOG": "dim white",
    "SEN": "bright_green",
    "NTP": "blue",
    "UPL": "magenta",
}

_PREFIX_RE = re.compile(r"^([A-Z]{2,4}):")

# Matches "WIF: ..." with or without a Tasmota timestamp prefix
# e.g. "WIF: Connected..." or "12:34:56.789 WIF: Connected..."
_WIF_RE = re.compile(r'WIF:\s*(.*)')

# Matches "AP1 SSID" or "AP 1 SSID" (Tasmota uses both)
_AP_SSID_RE = re.compile(r'AP\s*\d+\s+(\S+)')


def _colorize_line(line: str) -> str:
    m = _PREFIX_RE.match(line)
    if m:
        prefix = m.group(1)
        color = _PREFIX_COLORS.get(prefix, "white")
        rest = line[m.end():]
        if "Connected" in rest or "Online" in rest:
            color = "bold green"
        elif "Fail" in rest or "Error" in rest or "error" in rest:
            color = "bold red"
        return f"[{color}]{prefix}:[/{color}]{rest}"
    return line


class SerialTab(TabPane):
    """Real-time serial port monitor."""

    DEFAULT_CSS = ""
    connected: reactive[bool] = reactive(False)

    # Partial buffer for multi-line Status 5 response (rare, but safe)
    _status5_buf: str = ""
    _collecting_status5: bool = False
    _status5_reset_on_next: bool = False  # guards against stuck flag

    def compose(self) -> ComposeResult:
        with Vertical(id="serial-tab"):
            # --- Connection controls ------------------------------------
            with Horizontal(id="serial-controls"):
                yield Label("Port:", classes="label")
                yield Select(
                    options=[("– Keresés… –", "__none")],
                    id="serial-port-select",
                    allow_blank=False,
                )
                yield Label("Baud:", classes="label")
                yield Select(
                    options=[(str(b), b) for b in BAUD_RATES],
                    value=115200,
                    id="serial-baud-select",
                    allow_blank=False,
                )
                yield Button("Csatlakozás", id="serial-connect-btn", variant="success")
                yield Button("↺", id="serial-refresh-ports", variant="default")
                yield Button("Törlés", id="serial-clear-btn", variant="default")
                yield Label("", id="serial-status-label")

            # --- WiFi status bar ----------------------------------------
            with Horizontal(id="serial-wifi-bar"):
                yield Static("WiFi:", classes="label")
                yield Label("–", id="serial-wifi-status")

            # --- Quick commands -----------------------------------------
            with Horizontal(id="serial-quick-cmds"):
                yield Static("Gyors:", classes="label")
                for label, cmd, _ in QUICK_COMMANDS:
                    yield Button(label, id=f"qcmd_{cmd.replace(' ', '_')}", variant="default")

            # --- Output log ---------------------------------------------
            yield RichLog(
                id="serial-output",
                markup=True,
                highlight=False,
                auto_scroll=True,
            )

            # --- Command input ------------------------------------------
            with Horizontal(id="serial-input-row"):
                yield Label(">", classes="label")
                yield Input(
                    placeholder="Tasmota parancs (pl. Status 5, TelePeriod 60, Restart 1)",
                    id="serial-cmd-input",
                )
                yield Button("↵ Küldés", id="serial-send-btn", variant="primary")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh_ports()
        self.run_worker(self._serial_reader(), exclusive=True, name="serial_reader")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "serial-connect-btn":
            self._toggle_connection()
        elif btn_id == "serial-refresh-ports":
            self._refresh_ports()
        elif btn_id == "serial-send-btn":
            self._send_command()
        elif btn_id == "serial-clear-btn":
            log: RichLog = self.query_one("#serial-output")
            log.clear()
        elif btn_id.startswith("qcmd_"):
            # Find matching quick command
            cmd_key = btn_id[5:].replace("_", " ")
            for _, cmd, _ in QUICK_COMMANDS:
                if cmd == cmd_key:
                    self._send_direct(cmd)
                    break

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "serial-cmd-input":
            self._send_command()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _toggle_connection(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        btn: Button = self.query_one("#serial-connect-btn")
        lbl: Label = self.query_one("#serial-status-label")

        if serial_bridge.is_connected:
            serial_bridge.disconnect()
            self.connected = False
            btn.label = "Csatlakozás"
            btn.variant = "success"
            lbl.update("Lecsatlakozva")
            self._log_line("[dim]── Kapcsolat bontva ──[/dim]")
            self._set_wifi_status(None, None, None, None)
        else:
            port = self._selected_port()
            baud = self._selected_baud()
            if not port:
                lbl.update("[red]Nincs port kiválasztva![/red]")
                return
            try:
                serial_bridge.connect(port, baud)
                self.connected = True
                btn.label = "Lecsatlakozás"
                btn.variant = "error"
                lbl.update(f"[green]● {port}  {baud} baud[/green]")
                self._log_line(f"[green]── Kapcsolódva: {port} ({baud} baud) ──[/green]")
            except Exception as exc:
                lbl.update(f"[red]Hiba: {exc}[/red]")

    def _send_command(self) -> None:
        inp: Input = self.query_one("#serial-cmd-input")
        cmd = inp.value.strip()
        if not cmd:
            return
        self._send_direct(cmd)
        inp.value = ""

    def _send_direct(self, cmd: str) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if not serial_bridge.is_connected:
            self._log_line("[red]Nincs soros port kapcsolat![/red]")
            return
        try:
            serial_bridge.send(cmd)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
            self._log_line(f"[dim]{ts}[/dim]  [yellow]> {cmd}[/yellow]")
        except Exception as exc:
            self._log_line(f"[red]Küldési hiba: {exc}[/red]")

    # ------------------------------------------------------------------
    # Background serial reader
    # ------------------------------------------------------------------

    async def _serial_reader(self) -> None:
        import asyncio
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        while True:
            try:
                line = await serial_bridge.queue.get()
            except Exception:
                await asyncio.sleep(0.1)
                continue

            ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
            colored = _colorize_line(line)
            self._log_line(f"[dim]{ts}[/dim]  {colored}")

            # Parse WiFi info from live output and Status 5 response
            self._parse_wifi_from_line(line)
            # Detect chip from boot log or Status 2 response
            self._detect_chip_from_line(line)

    # ------------------------------------------------------------------
    # WiFi status parsing
    # ------------------------------------------------------------------

    def _parse_wifi_from_line(self, line: str) -> None:
        """
        Extract WiFi info from Tasmota serial output.
        Sources:
        - WIF: lines (live connection events, with or without timestamp prefix)
        - Status 5 JSON response (StatusNET block)
        - tele STATE / Status 11 lines with "Wifi" key
        """
        # --- Live WIF: log lines ---
        # Tasmota may prefix lines with a timestamp: "12:34:56 WIF: Connected..."
        # so we search for "WIF:" anywhere in the line, not just at the start.
        wif_m = _WIF_RE.search(line)
        if wif_m:
            rest = wif_m.group(1).strip()
            if "Connected" in rest:
                ip_m   = re.search(r"IP (\d+\.\d+\.\d+\.\d+)", rest)
                ssid_m = _AP_SSID_RE.search(rest)   # matches "AP1 SSID" or "AP 1 SSID"
                ip   = ip_m.group(1)   if ip_m   else None
                ssid = ssid_m.group(1) if ssid_m else None
                self._set_wifi_status(ssid, ip, None, "Csatlakozva")
                # Auto-fetch full details (RSSI + confirmed SSID)
                self._send_direct("Status 5")
            elif "Disconnect" in rest or "Fail" in rest:
                self._set_wifi_status(None, None, None, "Nincs kapcsolat")
            return

        # --- StatusNET JSON (Status 5 response) ---
        # Each new "StatusNET" line RESETS the buffer to prevent stale data
        # from a previous partial/failed parse from corrupting the next one.
        if "StatusNET" in line:
            self._collecting_status5 = True
            self._status5_buf = line + "\n"   # always reset on new response
            if "}" in line:
                self._try_parse_status5(self._status5_buf)
                self._collecting_status5 = False
                self._status5_buf = ""
            return

        if self._collecting_status5:
            self._status5_buf += line + "\n"
            if "}" in line:
                self._try_parse_status5(self._status5_buf)
                self._collecting_status5 = False
                self._status5_buf = ""
            # Safety: give up after 20 lines to avoid stuck state
            elif self._status5_buf.count("\n") > 20:
                self._collecting_status5 = False
                self._status5_buf = ""
            return

        # --- Inline JSON with Wifi key (tele STATE / Status 11) ---
        if '"Wifi"' in line:
            try:
                start = line.find("{")
                if start >= 0:
                    data = json.loads(line[start:])
                    wifi = data.get("Wifi", {})
                    if wifi:
                        # "Signal" is dBm (negative), "RSSI" is percentage (0-100)
                        rssi = self._normalise_rssi(
                            wifi.get("Signal"), wifi.get("RSSI")
                        )
                        ssid = wifi.get("SSId") or wifi.get("SSId1", "")
                        ip   = wifi.get("IPAddress", "")
                        if ssid:
                            self._set_wifi_status(ssid, ip or None, rssi, "Csatlakozva")
            except Exception:
                pass

    def _try_parse_status5(self, buf: str) -> None:
        """Parse accumulated Status 5 / StatusNET JSON block."""
        try:
            start = buf.find("{")
            if start < 0:
                return
            depth = 0
            end = -1
            for i, ch in enumerate(buf[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end < 0:
                return

            data = json.loads(buf[start:end])
            net  = data.get("StatusNET", data)
            # "Signal" = dBm, "RSSI" = percentage – normalise to dBm
            rssi = self._normalise_rssi(net.get("Signal"), net.get("RSSI"))
            ssid = net.get("SSId", "")
            ip   = net.get("IPAddress", "")
            if ssid or ip:
                self._set_wifi_status(
                    ssid or None, ip or None, rssi,
                    "Csatlakozva" if (ssid or ip) else None,
                )
        except Exception:
            pass

    @staticmethod
    def _normalise_rssi(
        signal: Optional[int], rssi_pct: Optional[int]
    ) -> Optional[int]:
        """
        Return RSSI in dBm.

        Tasmota uses two RSSI fields depending on context:
        - "Signal"  : dBm  (negative, e.g. -65)  – preferred
        - "RSSI"    : quality percentage (0-100)  – fallback
          Approximate conversion: dBm ≈ RSSI% / 2 - 100
        """
        if signal is not None:
            return int(signal)
        if rssi_pct is not None:
            pct = int(rssi_pct)
            if pct < 0:        # already dBm (some older Tasmota builds)
                return pct
            return pct // 2 - 100   # percentage → dBm
        return None

    def _set_wifi_status(
        self,
        ssid: Optional[str],
        ip: Optional[str],
        rssi: Optional[int],
        state: Optional[str],
    ) -> None:
        lbl: Label = self.query_one("#serial-wifi-status")
        if state is None or state == "Nincs kapcsolat":
            lbl.update("[red]● Nincs WiFi kapcsolat[/red]")
            return

        parts: list[str] = []
        if state:
            parts.append(f"[green]● {state}[/green]")
        if ssid:
            parts.append(f"SSID: [bold]{ssid}[/bold]")
        if ip:
            parts.append(f"IP: [cyan]{ip}[/cyan]")
        if rssi is not None:
            bars = rssi_to_bars(int(rssi))
            quality = rssi_label(int(rssi))
            color = "green" if int(rssi) > -70 else "yellow" if int(rssi) > -80 else "red"
            parts.append(
                f"Jelerősség: [{color}]{bars}[/{color}] {rssi} dBm ({quality})"
            )
        lbl.update("   ".join(parts) if parts else "–")

    # ------------------------------------------------------------------
    # Chip detection from serial output
    # ------------------------------------------------------------------

    def _detect_chip_from_line(self, line: str) -> None:
        """
        Identify chip family from Tasmota boot/status output.

        Sources:
        - Status 2 response: {"StatusFWR": {"Hardware": "ESP8266EX"}}
        - Boot log: "ESP-IDF" marker → ESP32 family
        - Boot log: "ets Jan  8 2013" → ESP8266
        - Boot log: "ESP32" in APP line
        """
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        chip: Optional[str] = None

        # Status 2 JSON
        if "StatusFWR" in line:
            start = line.find("{")
            if start >= 0:
                try:
                    data = json.loads(line[start:])
                    hw = data.get("StatusFWR", {}).get("Hardware", "")
                    if "ESP32-S3" in hw:
                        chip = "ESP32-S3"
                    elif "ESP32-C3" in hw:
                        chip = "ESP32-C3"
                    elif "ESP32" in hw:
                        chip = "ESP32"
                    elif "8266" in hw or "ESP8266" in hw:
                        chip = "ESP8266"
                except Exception:
                    pass

        # Boot markers
        if chip is None:
            if "ESP-IDF" in line:
                chip = "ESP32"
            elif "ets Jan  8 2013" in line or "ets_main.c" in line:
                chip = "ESP8266"

        # APP line sometimes contains chip info
        if chip is None and line.startswith("APP:"):
            if "ESP32S3" in line or "ESP32-S3" in line:
                chip = "ESP32-S3"
            elif "ESP32" in line:
                chip = "ESP32"

        if chip and chip != serial_bridge.detected_chip:
            serial_bridge.detected_chip = chip
            lbl: Label = self.query_one("#serial-status-label")
            current = lbl.renderable if hasattr(lbl, "renderable") else ""
            # Append chip badge if not already shown
            self._log_line(
                f"[dim]── Chip azonosítva: [bold cyan]{chip}[/bold cyan] ──[/dim]"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        sel: Select = self.query_one("#serial-port-select")
        if ports:
            sel.set_options([(p.display_label(), p.device) for p in ports])
        else:
            sel.set_options([("– Nincs eszköz –", "__none")])

    def _selected_port(self) -> Optional[str]:
        sel: Select = self.query_one("#serial-port-select")
        v = sel.value
        return None if v == "__none" or v is Select.BLANK else str(v)

    def _selected_baud(self) -> int:
        sel: Select = self.query_one("#serial-baud-select")
        v = sel.value
        return int(v) if v and v is not Select.BLANK else 115200

    def _log_line(self, line: str) -> None:
        log: RichLog = self.query_one("#serial-output")
        log.write(line)


class SerialLineReceived:
    """Custom message to forward serial lines to other tabs."""
    def __init__(self, line: str) -> None:
        self.line = line
