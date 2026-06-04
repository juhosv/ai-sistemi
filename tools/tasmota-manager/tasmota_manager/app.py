"""TasmoApp – main Textual application."""
from __future__ import annotations

from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Select, TabbedContent, TabPane

from tasmota_manager.board_layouts import BOARD_BY_NAME
from tasmota_manager.mqtt_client import MQTTManager
from tasmota_manager.serial_comm import AsyncSerialBridge
from tasmota_manager.screens.flash_screen import FlashTab
from tasmota_manager.screens.serial_screen import SerialTab
from tasmota_manager.screens.config_screen import ConfigTab
from tasmota_manager.screens.mqtt_screen import MQTTTab
from tasmota_manager.screens.board_screen import BoardTab

CSS_PATH = Path(__file__).parent.parent / "tasmota_manager.tcss"


class TasmoApp(App):
    """SmartBlue Tasmota Device Manager."""

    CSS_PATH = str(CSS_PATH)

    BINDINGS = [
        Binding("f1", "switch_tab('flash')",   "Flash",   show=True),
        Binding("f2", "switch_tab('serial')",  "Serial",  show=True),
        Binding("f3", "switch_tab('config')",  "Config",  show=True),
        Binding("f4", "switch_tab('mqtt')",    "MQTT",    show=True),
        Binding("f5", "switch_tab('board')",   "Board",   show=True),
        Binding("ctrl+s", "save_config",       "Mentés",  show=True),
        Binding("q", "quit",                   "Kilépés", show=True),
    ]

    # ------------------------------------------------------------------
    # Shared state – accessible from all tabs via self.app.*
    # ------------------------------------------------------------------

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serial_bridge = AsyncSerialBridge()
        self.mqtt_manager = MQTTManager()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            yield FlashTab("⚡ Flash",  id="flash")
            yield SerialTab("🖥 Serial", id="serial")
            yield ConfigTab("⚙ Config", id="config")
            yield MQTTTab("📡 MQTT",   id="mqtt")
            yield BoardTab("🔌 Board",  id="board")
        yield Footer()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id

    def action_save_config(self) -> None:
        try:
            config_tab: ConfigTab = self.query_one(ConfigTab)
            config_tab._save_profile()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # App title
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.title = "SmartBlue Tasmota Manager"
        self.sub_title = "ESP32 / ESP8266 eszközkezelő"

    # ------------------------------------------------------------------
    # GPIO sync: Config tab → Board tab
    # ------------------------------------------------------------------

    def sync_gpio_to_board(self) -> None:
        """Push GPIO assignments from ConfigTab into BoardTab (only if no device data yet)."""
        try:
            from tasmota_manager.screens.config_screen import ConfigTab
            from tasmota_manager.screens.board_screen import BoardTab
            cfg_tab: ConfigTab = self.query_one(ConfigTab)
            board_tab: BoardTab = self.query_one(BoardTab)
            board_tab.update_gpio_assignments(cfg_tab._get_gpio_assignments(),
                                              from_device=False)
        except Exception:
            pass

    def on_tabbed_content_tab_activated(self, event) -> None:  # type: ignore[override]
        """When Board tab opens: only pre-fill GPIO from Config if board has none yet."""
        if getattr(event, "tab", None) and getattr(event.tab, "id", None) == "board":
            try:
                from tasmota_manager.screens.board_screen import BoardTab
                board_tab: BoardTab = self.query_one(BoardTab)
                # Only copy from Config if no device data has been loaded yet
                if not board_tab._gpio_assignments:
                    self.sync_gpio_to_board()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Cross-tab sync: Config "Modul/Board" ↔ Board "Board" select
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        """Keep Config #cfg-module and Board #board-type-select in sync."""
        sel_id = event.select.id
        value = event.value
        if value is Select.BLANK:
            return

        board_name = str(value)

        if sel_id == "cfg-module":
            # Config changed → update Board (only if it's a known board layout)
            if board_name in BOARD_BY_NAME:
                try:
                    board_sel: Select = self.query_one("#board-type-select")
                    if board_sel.value != board_name:
                        board_sel.value = board_name
                except Exception:
                    pass

        elif sel_id == "board-type-select":
            # Board changed → update Config
            try:
                cfg_sel: Select = self.query_one("#cfg-module")
                if cfg_sel.value != board_name:
                    cfg_sel.value = board_name
            except Exception:
                pass
