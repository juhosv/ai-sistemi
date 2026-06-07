"""
Generate terminal-style mockup screenshots for the Tasmota Manager user guide.
Uses Pillow + Consolas font to render each tab as it appears in the TUI.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent / "screenshots"
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Colour palette (Textual default dark theme)
# ---------------------------------------------------------------------------
BG        = (13,  17,  23)    # #0D1117  – terminal background
BG2       = (22,  27,  34)    # panel background (slightly lighter)
BG3       = (33,  38,  45)    # header / tab bar
FG        = (201, 209, 217)   # #C9D1D9  – normal text
DIM       = (110, 118, 129)   # muted / dim text
GREEN     = ( 63, 185, 120)   # success
YELLOW    = (210, 153,  34)   # warning
RED       = (248,  81,  73)   # error
CYAN      = ( 88, 166, 255)   # info / link
BLUE      = ( 56, 139, 253)   # primary button
PURPLE    = (188, 140, 255)   # accent
ORANGE    = (255, 165,  60)   # warning alt
WHITE     = (255, 255, 255)
TAB_ACT   = ( 56, 139, 253)   # active tab text
TAB_INACT = (110, 118, 129)   # inactive tab text
BORDER    = ( 48,  54,  61)   # box border colour
BTN_DEF   = ( 48,  54,  61)   # default button bg
BTN_PRI   = ( 31,  111, 235)  # primary button bg
BTN_SUC   = ( 35, 134,  54)   # success button bg
BTN_ERR   = (185,  74,  72)   # error/danger button bg
BTN_WARN  = (187, 128,  38)   # warning button bg
INPUT_BG  = ( 33,  38,  45)   # input field bg
INPUT_BOR = ( 56, 139, 253)   # input border (focused)

FONT_PATH = "C:/Windows/Fonts/consola.ttf"

# ---------------------------------------------------------------------------
# Renderer helper
# ---------------------------------------------------------------------------
class Screen:
    CHAR_W = 9    # Consolas 14pt character width
    CHAR_H = 18   # Consolas 14pt line height

    def __init__(self, cols: int = 110, rows: int = 46):
        self.cols = cols
        self.rows = rows
        W = cols * self.CHAR_W + 20
        H = rows * self.CHAR_H + 20
        self.img  = Image.new("RGB", (W, H), BG)
        self.draw = ImageDraw.Draw(self.img)
        self.font      = ImageFont.truetype(FONT_PATH, 14)
        self.font_bold = ImageFont.truetype(FONT_PATH, 14)  # same – bold variant
        self.font_sm   = ImageFont.truetype(FONT_PATH, 12)

    # --- primitives ---------------------------------------------------------

    def px(self, col: int, row: int) -> tuple[int, int]:
        return (10 + col * self.CHAR_W, 10 + row * self.CHAR_H)

    def text(self, col: int, row: int, txt: str, color=FG, font=None):
        self.draw.text(self.px(col, row), txt, fill=color, font=font or self.font)

    def rect(self, col: int, row: int, w: int, h: int, fill=BG2, outline=BORDER):
        x1, y1 = self.px(col, row)
        x2 = x1 + w * self.CHAR_W
        y2 = y1 + h * self.CHAR_H
        self.draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline)

    def button(self, col: int, row: int, label: str, variant="default"):
        bg = {
            "default": BTN_DEF, "primary": BTN_PRI,
            "success": BTN_SUC, "error":   BTN_ERR,
            "warning": BTN_WARN,
        }.get(variant, BTN_DEF)
        w = len(label) + 2
        self.rect(col, row, w, 1, fill=bg, outline=bg)
        self.text(col + 1, row, label, WHITE)
        return w

    def input_field(self, col: int, row: int, width: int, value: str = "", placeholder: str = ""):
        self.rect(col, row, width, 1, fill=INPUT_BG, outline=INPUT_BOR)
        if value:
            self.text(col + 1, row, value[:width-2], FG)
        elif placeholder:
            self.text(col + 1, row, placeholder[:width-2], DIM)

    def label(self, col: int, row: int, txt: str, color=DIM):
        self.text(col, row, txt, color)

    def section_title(self, col: int, row: int, txt: str):
        self.text(col, row, txt, CYAN)
        underline_y = 10 + row * self.CHAR_H + self.CHAR_H - 2
        x1 = 10 + col * self.CHAR_W
        x2 = x1 + len(txt) * self.CHAR_W
        self.draw.line([(x1, underline_y), (x2, underline_y)], fill=CYAN, width=1)

    def hline(self, col: int, row: int, width: int, color=BORDER):
        y = 10 + row * self.CHAR_H + self.CHAR_H // 2
        x1 = 10 + col * self.CHAR_W
        x2 = x1 + width * self.CHAR_W
        self.draw.line([(x1, y), (x2, y)], fill=color)

    def select(self, col: int, row: int, width: int, value: str = "", prompt: str = ""):
        self.rect(col, row, width, 1, fill=INPUT_BG, outline=INPUT_BOR)
        txt = value if value else prompt
        color = FG if value else DIM
        self.text(col + 1, row, txt[:width-3], color)
        self.text(col + width - 2, row, "▼", DIM)

    def notification(self, col: int, row: int, msg: str, severity="information"):
        color = {
            "information": CYAN, "warning": YELLOW,
            "error": RED, "success": GREEN,
        }.get(severity, FG)
        bg = {
            "information": (20, 40, 60), "warning": (50, 40, 10),
            "error": (60, 20, 20), "success": (20, 50, 30),
        }.get(severity, BG2)
        w = len(msg) + 4
        self.rect(col, row, w, 1, fill=bg, outline=color)
        self.text(col + 2, row, msg, color)

    def tab_bar(self, tabs: list[str], active: int):
        """Draw the tab bar across the full width."""
        self.rect(0, 0, self.cols, 2, fill=BG3, outline=BG3)
        self.text(2, 0, "SmartBlue Tasmota Manager", CYAN)
        col = 2
        for i, tab in enumerate(tabs):
            is_active = (i == active)
            color = WHITE if is_active else TAB_INACT
            bg = BTN_PRI if is_active else BG3
            w = len(tab) + 2
            self.rect(col, 1, w, 1, fill=bg, outline=bg)
            self.text(col + 1, 1, tab, color)
            col += w + 1
        # keyboard hint
        self.text(self.cols - 18, 1, "Q Kilépés", DIM)

    def save(self, name: str):
        path = OUT_DIR / name
        self.img.save(path)
        print(f"  Saved: {path.name}  ({self.img.width}x{self.img.height})")

TABS = ["⚡ Flash", "🖥 Kapcsolat", "⚙ Config", "🔌 Board", "📡 MQTT", "📋 Rules"]


# ===========================================================================
# 00 – Főképernyő (Config tab overview)
# ===========================================================================
def gen_main():
    s = Screen(112, 10)
    s.tab_bar(TABS, 2)
    s.text(2, 4, "SmartBlue Tasmota Manager  –  IoT eszközök konfigurálása", CYAN)
    s.text(2, 6, "Navigáció:  F1-F6 billentyűkkel válthat tabok között", DIM)
    s.text(2, 7, "Kilépés:    Q billentyű", DIM)
    s.save("00-fokepernyő.png")


# ===========================================================================
# 01 – Flash tab
# ===========================================================================
def gen_flash():
    s = Screen(112, 36)
    s.tab_bar(TABS, 0)
    row = 3
    s.section_title(2, row, "Firmware égetés"); row += 2

    s.label(2, row, "Port:");    s.select(10, row, 28, prompt="– Keresés… –")
    w = s.button(40, row, "↺ Frissítés"); row += 2

    s.section_title(2, row, "Firmware kiválasztása"); row += 2
    for fw in ["tasmota.bin  (ESP8266)", "tasmota32.bin  (ESP32)", "tasmota32s3.bin  (ESP32-S3)"]:
        s.text(4, row, "○  " + fw, DIM); row += 1
    s.text(4, row - 2, "●  tasmota32.bin  (ESP32)", FG)
    row += 2

    s.button(2, row, "⬇ Letöltés", "primary")
    s.button(18, row, "🔥 Égetés", "error")
    row += 2

    s.section_title(2, row, "Folyamat"); row += 2
    s.rect(2, row, 90, 4, fill=BG2)
    s.text(3, row + 1, "Tasmota v14.5.0 letöltve  (630 KB)", GREEN)
    s.text(3, row + 2, "Égetés:  [████████████████████░░░░░░░░░░]  68%", YELLOW)
    s.save("01-flash-tab.png")


# ===========================================================================
# 02 – Kapcsolat tab
# ===========================================================================
def gen_kapcsolat():
    s = Screen(112, 44)
    s.tab_bar(TABS, 1)
    row = 3

    # Serial section
    s.section_title(2, row, "Soros port kapcsolat"); row += 2
    s.label(2, row, "Soros:");  s.select(10, row, 22, "COM3  (CH340)")
    s.label(34, row, "Baud:");  s.select(40, row, 12, "115200")
    s.button(54, row, "Csatlakozás", "success")
    s.button(68, row, "↺", "default")
    s.button(72, row, "Törlés", "default")
    s.text(82, row, "● Csatlakozva", GREEN)
    row += 2

    s.label(2, row, "Log:"); s.text(8, row, "C:\\Users\\...\\tasmota_logs\\COM3_20260607.log", DIM)
    s.button(90, row, "📂", "default"); row += 1
    s.label(2, row, "WiFi:"); s.text(8, row, "HomeNetwork   IP: 192.168.1.45", GREEN); row += 2

    # HTTP section
    s.section_title(2, row, "HTTP kapcsolat (WiFi-n, IP alapján)"); row += 2
    s.label(2, row, "HTTP:")
    s.input_field(8, row, 24, placeholder="192.168.1.100")
    s.input_field(34, row, 20, placeholder="Jelszó (opcionális)")
    s.button(56, row, "Csatlakozás", "success")
    s.text(70, row, "● Nincs HTTP kapcsolat", DIM); row += 2

    # MQTT status
    s.label(2, row, "MQTT:"); s.text(8, row, "● Csatlakozva  broker.emqx.io:1883", GREEN)
    s.button(56, row, "→ MQTT tab", "default"); row += 2

    # Quick commands
    s.label(2, row, "Gyors:")
    col = 10
    for lbl in ["Status", "WiFi", "GPIO", "MQTT", "Újraind."]:
        w = s.button(col, row, lbl); col += w + 1
    row += 2

    # Log output
    s.rect(2, row, 108, 12, fill=BG2)
    logs = [
        ("00:00:01 ", "MQT: Connected to broker.emqx.io:1883", CYAN),
        ("00:00:01 ", "MQT: tele/viktor/szarvas/A1B2C3/LWT = Online", CYAN),
        ("00:00:02 ", "WIF: Connected to HomeNetwork", GREEN),
        ("00:00:02 ", "WIF: IP: 192.168.1.45, Mask: 255.255.255.0", GREEN),
        ("00:00:05 ", "tele/viktor/szarvas/A1B2C3/STATE → {\"POWER1\":\"OFF\"}", FG),
        ("00:00:06 ", "tele/viktor/szarvas/A1B2C3/SENSOR → {\"AM2301\":{\"Temperature\":23.4}}", FG),
        ("00:05:00 ", "tele/viktor/szarvas/A1B2C3/STATE → {\"POWER1\":\"OFF\"}", DIM),
    ]
    for i, (ts, msg, col_) in enumerate(logs):
        s.text(3, row + i, ts, DIM)
        s.text(3 + len(ts), row + i, msg, col_)
    row += 12

    # Command input
    s.text(2, row, ">", DIM)
    s.input_field(4, row, 90, placeholder="Tasmota parancs  (pl. Status 5, Restart 1)")
    s.button(96, row, "↵ Küldés", "primary")

    s.save("02-kapcsolat-serial.png")


# ===========================================================================
# 03 – Config tab (felső rész: WiFi + MQTT)
# ===========================================================================
def gen_config_alap():
    s = Screen(112, 50)
    s.tab_bar(TABS, 2)
    row = 3

    # Profile row
    s.label(2, row, "Profil:"); s.select(10, row, 28, "sonoff_basic_profil")
    s.button(40, row, "📂 Betöltés"); s.button(52, row, "💾 Mentés", "primary")
    s.input_field(63, row, 22, "uj_profil")
    s.button(87, row, "↺ Reset", "error")
    row += 2

    # Group row
    s.label(2, row, "User:"); s.select(8, row, 22, "viktor  (Viktor Juhos)")
    s.label(32, row, "Régió:"); s.select(39, row, 22, "szarvas  (Szarvas)")
    s.button(63, row, "⚙ Szerkesztés"); row += 2

    # Fetch row
    s.button(2, row, "📥 Konfiguráció letöltése az eszközről", "warning")
    s.text(46, row, "HTTP kapcsolat aktív", DIM)
    s.text(70, row, "✓ Feltöltve: WiFi, MQTT, GPIO, Board", GREEN)
    row += 2

    # WiFi + MQTT side by side
    # WiFi (left)
    s.section_title(2, row, "WiFi"); row += 1
    s.button(2, row, "📡 Szkennelés"); s.text(20, row, "4 hálózat találva", GREEN); row += 1

    s.rect(2, row, 50, 3, fill=BG2)  # scan results box
    s.text(3, row, "▼ HomeNetwork      (-52 dBm, WPA2)  ← kiválasztva", FG)
    s.text(3, row+1, "  GuestWifi        (-71 dBm, WPA2)", DIM)
    s.text(3, row+2, "  Szomszed-net     (-85 dBm, WPA2)", DIM)
    row += 3
    s.button(2, row, "→ SSID 1-be", "success"); s.button(16, row, "→ SSID 2-be"); row += 2

    s.label(2, row, "SSID 1:");    s.input_field(12, row, 36, "HomeNetwork"); row += 1
    s.label(2, row, "Jelszó 1:");  s.input_field(12, row, 36, "••••••••••••"); row += 1
    s.label(2, row, "SSID 2:");    s.input_field(12, row, 36, "", "Tartalék (opcionális)"); row += 1
    s.label(2, row, "Jelszó 2:");  s.input_field(12, row, 36, "", "••••••••"); row += 2

    # MQTT (right)
    mr = 10  # right side start row
    s.section_title(58, mr, "MQTT"); mr += 2
    s.label(58, mr, "Host:");     s.input_field(68, mr, 38, "192.168.1.10"); mr += 1
    s.label(58, mr, "Port:");     s.input_field(68, mr, 38, "1883"); mr += 1
    s.label(58, mr, "User:");     s.input_field(68, mr, 38, "smartblue"); mr += 1
    s.label(58, mr, "Jelszó:");   s.input_field(68, mr, 38, "••••••••"); mr += 1
    s.label(58, mr, "Eszköz ID:"); s.input_field(68, mr, 38, "A1B2C3"); mr += 1
    s.label(58, mr, "FullTopic:"); s.input_field(68, mr, 38, "viktor/szarvas/%topic%/%prefix%/"); mr += 1
    s.text(68, mr, "→  tele/viktor/szarvas/A1B2C3/SENSOR", DIM); mr += 2

    # Module
    s.section_title(58, mr, "Általános"); mr += 2
    s.label(58, mr, "Modul/Board:"); s.select(72, mr, 36, "ESP32 DevKit V1"); mr += 2

    # Send row
    s.button(2, row, "📡 Küldés eszközre", "primary")
    s.button(24, row, "📡 Küldés MQTT-n", "success")
    row += 2

    # Backup row
    s.button(2, row, "💾 Konfig backup")
    s.select(20, row, 36, "192_168_1_45_20260607_183045.dmp")
    s.button(58, row, "📤 Visszatöltés", "warning")
    s.button(74, row, "📋 Betöltés backup-ból")

    s.save("03-config-alap.png")


# ===========================================================================
# 03b – Config tab GPIO
# ===========================================================================
def gen_config_gpio():
    s = Screen(112, 48)
    s.tab_bar(TABS, 2)
    row = 3

    s.section_title(2, row, "GPIO kiosztás"); row += 2

    # Board diagram (left)
    s.section_title(2, row, "Board – ESP32 DevKit V1")
    s.text(52, row, "Pin beállítás  –  D2 / GPIO4", CYAN); row += 2

    # Draw a simplified ESP32 board
    board_pins_left = [
        ("3V3", None, None), ("GND", None, None), ("D15/GPIO15", 15, None),
        ("D2/GPIO2", 2, None), ("D4/GPIO4", 4, "relay"),
        ("RX/GPIO3", 3, "uart"), ("TX/GPIO1", 1, "uart"),
        ("D22/GPIO22", 22, None), ("D21/GPIO21", 21, None),
    ]
    board_pins_right = [
        ("VIN", None, None), ("GND", None, None), ("D13/GPIO13", 13, None),
        ("D12/GPIO12", 12, None), ("D14/GPIO14", 14, "ds18b20"),
        ("D27/GPIO27", 27, None), ("D26/GPIO26", 26, None),
        ("D25/GPIO25", 25, None), ("D33/GPIO33", 33, None),
    ]
    board_row = row
    s.rect(2, board_row, 28, len(board_pins_left) + 2, fill=BG2)
    for i, (name, gpio, func) in enumerate(board_pins_left):
        color = GREEN if func else (CYAN if "uart" in str(func or "") else FG)
        if name.startswith("GND") or name.startswith("3V3") or name.startswith("VIN"):
            color = RED if "3V" in name or "VIN" in name else DIM
        marker = " ●" if func else " ○"
        label_text = f" {marker} {name}"
        s.text(3, board_row + 1 + i, label_text, color)
        if func == "relay":
            s.text(20, board_row + 1 + i, "Relay1", GREEN)
        elif func == "ds18b20":
            s.text(20, board_row + 1 + i, "DS18B20", YELLOW)
    
    # Right column (selected pin highlighted)
    s.rect(52, row, 55, 18, fill=BG2)
    row2 = row + 1
    s.text(54, row2, "GPIO:   GPIO4  (D2)", FG); row2 += 1
    s.text(54, row2, "Típus:  Digitális kimenet", DIM); row2 += 2
    s.label(54, row2, "Funkció:"); row2 += 1
    s.select(54, row2, 48, "Relé kimenet  (Relay)"); row2 += 2
    s.text(54, row2, "A relé távolról kapcsolható MQTT-n:", DIM); row2 += 1
    s.text(54, row2, "cmnd/.../POWER1 ON / OFF", CYAN); row2 += 2
    s.text(54, row2, "MQTT üzenet be/ki állapotról:", DIM); row2 += 1
    s.text(54, row2, 'stat/.../RESULT → {"POWER1":"ON"}', CYAN); row2 += 2
    s.button(54, row2, "✓ Beállítás", "success")
    s.button(68, row2, "✗ Törlés", "warning")

    # Preview table
    prow = board_row + len(board_pins_left) + 3
    s.section_title(2, prow, "Tasmota parancsok előnézete"); prow += 2
    headers = ["Parancs", "Érték"]
    cmds = [
        ("Module",   "0"),
        ("Mem1",     "ESP32 DevKit V1"),
        ("GPIO4",    "224  (= Relay1)"),
        ("GPIO14",   "8    (= DS18B20)"),
        ("Restart",  "1"),
    ]
    s.rect(2, prow, 60, len(cmds) + 2, fill=BG2)
    s.text(4, prow, "Parancs", CYAN); s.text(24, prow, "Érték", CYAN); prow += 1
    s.hline(2, prow, 60, BORDER)
    for cmd, val in cmds:
        s.text(4, prow, cmd, FG); s.text(24, prow, val, YELLOW); prow += 1

    s.save("03-config-gpio.png")


# ===========================================================================
# 04 – MQTT Monitor
# ===========================================================================
def gen_mqtt():
    s = Screen(112, 48)
    s.tab_bar(TABS, 4)
    row = 3

    # Connection bar
    s.label(2, row, "Host:"); s.input_field(8, row, 26, "192.168.1.10")
    s.label(36, row, "Port:"); s.input_field(42, row, 8, "1883")
    s.label(52, row, "User:"); s.input_field(58, row, 14, "smartblue")
    s.label(74, row, "Topic:"); s.input_field(81, row, 14, "#")
    s.button(97, row, "Csatlakozás", "success"); row += 1
    s.text(2, row, "● Csatlakozva  192.168.1.10:1883", GREEN); row += 2

    # Three panels
    # Left: topic tree
    s.section_title(2, row, "Topic fa")
    s.section_title(36, row, "Üzenet – tele/viktor/szarvas/A1B2C3/SENSOR")
    row += 2

    tree_items = [
        (0, "▼ viktor/", FG),
        (1, "▼ szarvas/", FG),
        (2, "▼ A1B2C3  ● Online", GREEN),
        (3, "  tele/…/STATE", DIM),
        (3, "  tele/…/SENSOR  ← kiválasztva", CYAN),
        (3, "  stat/…/RESULT", DIM),
        (3, "  cmnd/…/POWER1", DIM),
        (2, "▼ B3C4D5  ● Online", GREEN),
        (3, "  tele/…/STATE", DIM),
        (3, "  tele/…/SENSOR", DIM),
        (2, "▷ C5D6E7  ○ Offline", DIM),
    ]
    for i, (indent, txt, col) in enumerate(tree_items):
        s.text(2 + indent * 2, row + i, txt, col)
    
    # Right: payload
    payload_lines = [
        ('{', FG),
        ('  "Time":  "2026-06-07T18:30:00",', DIM),
        ('  "AM2301": {', FG),
        ('    "Temperature": 23.4,', YELLOW),
        ('    "Humidity":    61.2', YELLOW),
        ('  },', FG),
        ('  "Switch1": "OFF"', FG),
        ('}', FG),
    ]
    s.rect(36, row, 74, len(payload_lines) + 2, fill=BG2)
    for i, (line, col) in enumerate(payload_lines):
        s.text(38, row + 1 + i, line, col)

    row += 14

    # Filter bar
    s.label(2, row, "Szűrő:"); s.button(10, row, "tele"); s.button(16, row, "stat"); s.button(22, row, "cmnd")
    s.button(30, row, "▼ Minden prefix", "default"); row += 2

    # Log
    s.section_title(2, row, "Üzenetnapló"); row += 1
    s.rect(2, row, 108, 9, fill=BG2)
    log_items = [
        ("18:30:01 ", "tele/viktor/szarvas/A1B2C3/STATE   ", '{"POWER1":"OFF","Wifi":{"RSSI":74}}'),
        ("18:30:01 ", "tele/viktor/szarvas/A1B2C3/SENSOR  ", '{"AM2301":{"Temperature":23.4,"Humidity":61.2}}'),
        ("18:30:02 ", "tele/viktor/szarvas/B3C4D5/STATE   ", '{"POWER1":"ON"}'),
        ("18:35:01 ", "tele/viktor/szarvas/A1B2C3/STATE   ", '{"POWER1":"OFF"}'),
        ("18:35:45 ", "tele/viktor/szarvas/A1B2C3/SENSOR  ", '{"Switch1":"ON"}'),
        ("18:35:46 ", "stat/viktor/szarvas/A1B2C3/RESULT  ", '{"POWER1":"ON"}'),
    ]
    for i, (ts, topic, payload) in enumerate(log_items):
        s.text(3, row + i, ts, DIM)
        s.text(3 + len(ts), row + i, topic, CYAN)
        s.text(3 + len(ts) + len(topic), row + i, payload[:40], FG)

    s.save("04-mqtt-monitor.png")


# ===========================================================================
# 05 – Board tab
# ===========================================================================
def gen_board():
    s = Screen(112, 50)
    s.tab_bar(TABS, 3)
    row = 3

    # Controls
    s.label(2, row, "Board:"); s.select(9, row, 24, "ESP32 DevKit V1")
    s.label(35, row, "Forrás:");
    s.text(43, row, "● MQTT", GREEN); s.text(52, row, "○ Soros/HTTP", DIM)
    s.text(68, row, "Uptime: 0T 02:14:37", DIM)
    s.button(84, row, "↺ Lekérés", "primary"); s.button(97, row, "GPIO diagn.", "default"); row += 2

    # Board diagram
    s.section_title(2, row, "Board – ESP32 DevKit V1"); row += 2
    pins_l = [
        ("3V3",    None,  None,   "pow"),
        ("GND",    None,  None,   "pow"),
        ("D15",    15,    None,   ""),
        ("D2",     2,     None,   ""),
        ("D4",     4,     True,   "relay"),   # relay ON
        ("D0",     0,     None,   ""),
        ("D5",     5,     False,  "switch"),  # switch OFF
        ("D18",    18,    None,   ""),
        ("TX",     1,     None,   "uart"),
        ("RX",     3,     None,   "uart"),
    ]
    for i, (name, gpio, state, func) in enumerate(pins_l):
        if func == "pow":
            s.text(3, row + i, f"  {name:<8}", RED)
        elif func == "relay":
            s.text(3, row + i, f"■ {name:<6} Relay1", GREEN)
        elif func == "switch":
            s.text(3, row + i, f"□ {name:<6} Switch1", DIM)
        elif func == "uart":
            s.text(3, row + i, f"  {name:<8}", CYAN)
        else:
            s.text(3, row + i, f"○ {name:<8}", DIM)

    # Right panel: device info
    pr = row
    s.rect(50, pr, 60, 30, fill=BG2)
    s.section_title(52, pr, "Eszköz"); pr += 2
    info = [
        ("Hostname:",  "tasmota-A1B2C3"),
        ("Topic:",     "A1B2C3"),
        ("Firmware:",  "14.5.0(tasmota)"),
        ("Hardware:",  "ESP32-D0WD"),
        ("Memória:",   "187 KB szabad"),
        ("Board:",     "ESP32 DevKit V1"),
    ]
    for k, v in info:
        s.text(52, pr, k, DIM); s.text(64, pr, v, FG); pr += 1
    pr += 1

    s.section_title(52, pr, "WiFi"); pr += 2
    s.text(52, pr, "SSID:", DIM);   s.text(64, pr, "HomeNetwork", FG); pr += 1
    s.text(52, pr, "IP:",   DIM);   s.text(64, pr, "192.168.1.45", FG); pr += 1
    s.text(52, pr, "Jel:",  DIM);   s.text(64, pr, "-52 dBm  (jó)", GREEN); pr += 2

    s.section_title(52, pr, "MQTT"); pr += 2
    s.text(52, pr, "Broker:", DIM); s.text(64, pr, "192.168.1.10:1883", FG); pr += 1
    s.text(52, pr, "Client:", DIM); s.text(64, pr, "tasmota-A1B2C3", FG); pr += 2

    s.section_title(52, pr, "Kimenetek – vezérlés"); pr += 2
    s.text(52, pr, "Relay1  (GPIO4)", FG)
    s.button(68, pr, "BE",  "success"); s.button(73, pr, "KI",  "error"); pr += 2

    s.section_title(52, pr, "Szenzor"); pr += 2
    s.text(52, pr, "DS18B20:", DIM);  s.text(64, pr, "23.4 °C", YELLOW); pr += 1
    s.text(52, pr, "Switch1:", DIM);  s.text(64, pr, "OFF", DIM); pr += 1

    # Pin table
    table_row = row + len(pins_l) + 2
    s.section_title(2, table_row, "Pin állapot táblázat"); table_row += 1
    s.rect(2, table_row, 44, 6, fill=BG2)
    s.text(3,  table_row, "GPIO", CYAN); s.text(10, table_row, "Pin", CYAN)
    s.text(18, table_row, "Funkció", CYAN); s.text(30, table_row, "Állapot", CYAN); table_row += 1
    rows_t = [("GPIO4", "D4",  "Relay1",  "■ ON",  GREEN),
              ("GPIO5", "D5",  "Switch1", "□ OFF", DIM),
              ("GPIO14","D14", "DS18B20", "23.4°C",YELLOW),
              ("GPIO1", "TX",  "UART TX", "–",      CYAN),
              ("GPIO3", "RX",  "UART RX", "–",      CYAN)]
    for g, p, f, st, sc in rows_t:
        s.text(3,  table_row, g, FG); s.text(10, table_row, p, FG)
        s.text(18, table_row, f, FG); s.text(30, table_row, st, sc)
        table_row += 1

    s.save("05-board-monitor.png")


# ===========================================================================
# 06 – Rules tab
# ===========================================================================
def gen_rules():
    s = Screen(112, 46)
    s.tab_bar(TABS, 5)
    row = 3

    s.section_title(2, row, "Automatizálási szabályok (Tasmota Rules)"); row += 2
    s.text(2, row, "Triggerek a Config tab GPIO kiosztásából kerülnek be automatikusan.", DIM); row += 2

    # Rule 1 (filled)
    s.rect(2, row, 108, 5, fill=BG2)
    s.text(3, row, "Szabály #1", CYAN)
    row += 1
    s.label(3, row, "Ha:"); s.select(7, row, 38, "DS18B20 – Hőmérséklet (G14)")
    s.select(47, row, 8, ">"); s.input_field(56, row, 8, "35")
    s.text(66, row, "°C", DIM); row += 1
    s.label(3, row, "Akkor:"); s.select(11, row, 32, "Relay 1 (G4)")
    s.select(45, row, 16, "BE – ON"); row += 1
    s.label(3, row, "Különben:"); s.select(14, row, 32, "Relay 1 (G4)")
    s.select(48, row, 16, "KI – OFF")
    s.button(67, row, "🗑", "error"); row += 2

    # Rule 2 (filled)
    s.rect(2, row, 108, 4, fill=BG2)
    s.text(3, row, "Szabály #2", CYAN); row += 1
    s.label(3, row, "Ha:"); s.select(7, row, 38, "Rendszer – Induláskor")
    s.text(47, row, "(nincs feltétel – esemény típusú)", DIM); row += 1
    s.label(3, row, "Akkor:"); s.select(11, row, 32, "Relay 1 (G4)")
    s.select(45, row, 16, "KI – OFF")
    s.button(64, row, "🗑", "error"); row += 2

    # Add new rule
    s.button(2, row, "+ Új szabály hozzáadása"); row += 2

    # Generated Rule preview
    s.section_title(2, row, "Generált Tasmota szintaxis"); row += 2
    s.rect(2, row, 108, 7, fill=BG2)
    rule_lines = [
        "Rule1",
        "  ON DS18B20#Temperature>35 DO POWER1 ON ENDON",
        "  ON DS18B20#Temperature<35 DO POWER1 OFF ENDON",
        "Rule2",
        "  ON System#Boot DO POWER1 OFF ENDON",
        "Rule1 1",
        "Rule2 1",
    ]
    for i, line in enumerate(rule_lines):
        s.text(4, row + i, line, CYAN if line.startswith("Rule") else FG)
    row += 8

    # Send button
    s.button(2, row, "📡 Küldés az eszközre", "primary")
    s.button(26, row, "Letöltés az eszközről", "warning")
    s.text(52, row, "3 szabály elküldje → Rule1, Rule2 aktív", GREEN)

    s.save("06-rules.png")


# ===========================================================================
# Main
# ===========================================================================
if __name__ == "__main__":
    print(f"Generating screenshots to: {OUT_DIR}")
    gen_main()
    gen_flash()
    gen_kapcsolat()
    gen_config_alap()
    gen_config_gpio()
    gen_mqtt()
    gen_board()
    gen_rules()
    print("Done!")
