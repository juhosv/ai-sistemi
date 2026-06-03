"""Flash tab – firmware download and esptool flashing."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Checkbox,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    TabPane,
)
from textual.worker import Worker, WorkerState, get_current_worker

from tasmota_manager.flasher import (
    FIRMWARE_VARIANTS,
    FirmwareVariant,
    ReleaseInfo,
    CACHE_DIR,
    get_latest_release,
    download_firmware,
    flash_firmware,
)
from tasmota_manager.utils import list_serial_ports


class FlashTab(TabPane):
    """Firmware download and flashing screen."""

    DEFAULT_CSS = ""

    release_info: reactive[Optional[ReleaseInfo]] = reactive(None)
    flash_busy: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Vertical(id="flash-tab"):
            # --- Port selection -----------------------------------------
            with Horizontal(id="flash-port-row"):
                yield Label("Port:", classes="label")
                yield Select(
                    options=[("– Keresés… –", "__none")],
                    id="flash-port-select",
                    allow_blank=False,
                )
                yield Button("↺ Frissítés", id="flash-refresh-ports", variant="default")
                yield Label("", id="flash-chip-label")

            # --- Firmware list ------------------------------------------
            with Vertical(classes="section"):
                yield Static("Firmware kiválasztása", classes="section-title")
                with RadioSet(id="flash-firmware-radio"):
                    for v in FIRMWARE_VARIANTS:
                        yield RadioButton(
                            f"{v.filename:<28}  {v.chip:<10}  {v.description}",
                            id=f"fw_{v.filename.replace('.', '_').replace('-', '_')}",
                        )
                with Horizontal(classes="btn-row"):
                    yield Button("⬇ Letöltés", id="flash-download-btn", variant="primary")
                    yield Button("🔥 Égetés", id="flash-flash-btn", variant="error")
                    yield Checkbox("Törlés égetés előtt", id="flash-erase-cb", value=True)

            # --- Progress -----------------------------------------------
            with Vertical(classes="section", id="flash-progress"):
                yield Static("Folyamat", classes="section-title")
                yield ProgressBar(id="flash-progressbar", total=100, show_eta=False)
                yield Label("Kész.", id="flash-status-label")

            # --- Log ----------------------------------------------------
            yield RichLog(id="flash-log", markup=True, highlight=True, auto_scroll=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh_ports()
        self.run_worker(self._fetch_release_info(), exclusive=True, name="fetch_release")

    # ------------------------------------------------------------------
    # Port helpers
    # ------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        sel: Select = self.query_one("#flash-port-select")
        if ports:
            options = [(p.display_label(), p.device) for p in ports]
            sel.set_options(options)
        else:
            sel.set_options([("– Nincs eszköz –", "__none")])

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "flash-refresh-ports":
            self._refresh_ports()
        elif btn_id == "flash-download-btn":
            self.run_worker(self._do_download(), exclusive=True, name="download")
        elif btn_id == "flash-flash-btn":
            self.run_worker(self._do_flash(), exclusive=True, name="flash")

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    async def _fetch_release_info(self) -> None:
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: get_latest_release(log_cb=self._log)
            )
            self.release_info = info
            self._log(f"[green]Legfrissebb verzió: {info.tag}[/green]")
        except Exception as exc:
            self._log(f"[red]Hiba a verzióinformáció letöltésekor: {exc}[/red]")

    async def _do_download(self) -> None:
        if self.release_info is None:
            self._log("[yellow]Még nincs verzióinformáció – várj a betöltésre.[/yellow]")
            return
        variant = self._selected_variant()
        if variant is None:
            self._log("[yellow]Válassz firmware-t![/yellow]")
            return

        url = self.release_info.assets.get(variant.filename)
        if url is None:
            self._log(f"[red]{variant.filename} nem található az assets között.[/red]")
            return

        dest = CACHE_DIR / variant.filename
        self._set_busy(True)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: download_firmware(
                    url,
                    dest,
                    progress_cb=self._update_progress_bytes,
                    log_cb=self._log,
                ),
            )
            self._log(f"[green]Letöltés kész: {dest}[/green]")
        except Exception as exc:
            self._log(f"[red]Letöltési hiba: {exc}[/red]")
        finally:
            self._set_busy(False)

    async def _do_flash(self) -> None:
        port = self._selected_port()
        if not port:
            self._log("[yellow]Válassz soros portot![/yellow]")
            return
        variant = self._selected_variant()
        if variant is None:
            self._log("[yellow]Válassz firmware-t![/yellow]")
            return
        fw_path = CACHE_DIR / variant.filename
        if not fw_path.exists():
            self._log("[yellow]Töltsd le először a firmware-t![/yellow]")
            return

        erase_cb: Checkbox = self.query_one("#flash-erase-cb")
        erase = erase_cb.value
        chip = variant.chip.lower().replace("-", "")
        self._set_busy(True)
        self._update_progress(0, 100)

        def _progress_adapter(downloaded: int, total: int) -> None:
            if total > 0:
                self._update_progress(int(downloaded * 100 / total), 100)

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: flash_firmware(
                    port=port,
                    firmware_path=fw_path,
                    chip=chip,
                    erase=erase,
                    log_cb=self._log,
                    progress_cb=_progress_adapter,
                ),
            )
            self._update_progress(100, 100)
            self._log("[green bold]Égetés sikeres! Az eszköz újraindul.[/green bold]")
        except Exception as exc:
            self._log(f"[red]Égetési hiba: {exc}[/red]")
        finally:
            self._set_busy(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_port(self) -> Optional[str]:
        sel: Select = self.query_one("#flash-port-select")
        v = sel.value
        return None if v == "__none" or v is Select.BLANK else str(v)

    def _selected_variant(self) -> Optional[FirmwareVariant]:
        rs: RadioSet = self.query_one("#flash-firmware-radio")
        idx = rs.pressed_index
        if idx is None or idx < 0 or idx >= len(FIRMWARE_VARIANTS):
            return None
        return FIRMWARE_VARIANTS[idx]

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # call_from_thread is only valid from a background thread;
    # async workers run on the event loop thread → call widgets directly.
    # ------------------------------------------------------------------

    def _in_app_thread(self) -> bool:
        import threading
        return threading.current_thread() is threading.main_thread()

    def _ui(self, fn, *args) -> None:
        """Call *fn(*args)* safely from any thread or async context."""
        if self._in_app_thread():
            fn(*args)
        else:
            self.app.call_from_thread(fn, *args)

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log: RichLog = self.query_one("#flash-log")
        self._ui(log.write, f"[dim]{ts}[/dim]  {msg}")

    def _update_progress(self, value: int, total: int) -> None:
        pb: ProgressBar = self.query_one("#flash-progressbar")
        lbl: Label = self.query_one("#flash-status-label")
        pct = int(value * 100 / total) if total else 0
        self._ui(setattr, pb, "progress", value)
        self._ui(setattr, pb, "total", total)
        self._ui(setattr, lbl, "renderable", f"{pct}%")

    def _update_progress_bytes(self, downloaded: int, total: int) -> None:
        pct = int(downloaded * 100 / total) if total else 0
        pb: ProgressBar = self.query_one("#flash-progressbar")
        lbl: Label = self.query_one("#flash-status-label")
        kb_done = downloaded // 1024
        kb_total = total // 1024
        self._ui(setattr, pb, "progress", pct)
        self._ui(setattr, lbl, "renderable", f"Letöltés: {kb_done} kB / {kb_total} kB")

    def _set_busy(self, busy: bool) -> None:
        self.flash_busy = busy
        for btn_id in ("#flash-download-btn", "#flash-flash-btn"):
            btn: Button = self.query_one(btn_id)
            self._ui(setattr, btn, "disabled", busy)
