# Képernyőképek frissítése

## Hogyan készíts új képernyőképet

1. Indítsd el a Tasmota Managert:
   ```
   cd tools\tasmota-manager
   python main.py
   ```
   vagy futtasd a `release\SmartBlue-TasmotaManager\SmartBlue-TasmotaManager.exe`-t

2. Navigálj a kívánt tabra / állapotba

3. Nyomj **Ctrl+PrintScreen** a terminálban → a Textual automatikusan SVG-t ment  
   (az SVG konvertálható PNG-vé pl. Inkscape-pel vagy online eszközzel)

4. Alternatíva: **Windows Snipping Tool** (Win+Shift+S) → PNG formátumban ments ide:
   `docs/user-guide/screenshots/`

## Fájlnév konvenció

| Fájlnév | Tartalom |
|---------|---------|
| `01-flash-tab.png` | Flash tab – firmware letöltés és égetés |
| `02-kapcsolat-serial.png` | Kapcsolat tab – soros port csatlakozás |
| `02-kapcsolat-http.png` | Kapcsolat tab – HTTP csatlakozás |
| `03-config-alap.png` | Config tab – WiFi és MQTT mezők |
| `03-config-gpio.png` | Config tab – GPIO kiosztás, board diagram |
| `03-config-csoportok.png` | Config tab – User/Region szerkesztő |
| `04-mqtt-monitor.png` | MQTT Monitor tab – topic fa és payload |
| `05-board-monitor.png` | Board tab – vizuális pin térkép |
| `06-rules.png` | Rules tab |

## Ha a UI megváltozott

Csak cseréld le a PNG fájlt ugyanolyan névvel – a guide automatikusan az újat mutatja.
