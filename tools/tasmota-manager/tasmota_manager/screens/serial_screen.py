"""Serial Monitor tab – real-time serial port monitor."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, RichLog, Select, TabPane

from tasmota_manager.utils import list_serial_ports

BAUD_RATES = [9600, 19200, 38400, 57600, 74880, 115200, 230400, 460800, 921600]

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
                    placeholder="Tasmota parancs (pl. Status, TelePeriod 60)",
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
        btn_id = event.button.id
        if btn_id == "serial-connect-btn":
            self._toggle_connection()
        elif btn_id == "serial-refresh-ports":
            self._refresh_ports()
        elif btn_id == "serial-send-btn":
            self._send_command()
        elif btn_id == "serial-clear-btn":
            log: RichLog = self.query_one("#serial-output")
            log.clear()

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
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        if not serial_bridge.is_connected:
            self._log_line("[red]Nincs soros port kapcsolat![/red]")
            return
        try:
            serial_bridge.send(cmd)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
            self._log_line(f"[dim]{ts}[/dim]  [yellow]> {cmd}[/yellow]")
            inp.value = ""
        except Exception as exc:
            self._log_line(f"[red]Küldési hiba: {exc}[/red]")

    # ------------------------------------------------------------------
    # Background serial reader
    # ------------------------------------------------------------------

    async def _serial_reader(self) -> None:
        serial_bridge = self.app.serial_bridge  # type: ignore[attr-defined]
        while True:
            try:
                line = await serial_bridge.queue.get()
            except Exception:
                import asyncio
                await asyncio.sleep(0.1)
                continue
            ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
            colored = _colorize_line(line)
            self._log_line(f"[dim]{ts}[/dim]  {colored}")
            # Notify board screen if possible
            try:
                self.app.post_message_no_wait(  # type: ignore[attr-defined]
                    SerialLineReceived(line)
                )
            except Exception:
                pass

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
