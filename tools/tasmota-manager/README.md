# SmartBlue Tasmota Device Manager

Python TUI eszköz ESP32 / ESP8266 Tasmota eszközök kezeléséhez.

## Indítás

```bash
# Python 3.10+ szükséges
py -3.10 -m pip install -r requirements.txt
py -3.10 main.py
```

## Funkciók

| Tab | Leírás |
|-----|--------|
| ⚡ **Flash** | Tasmota firmware letöltés (GitHub) és égetés (esptool) |
| 🖥 **Serial** | Soros port monitor, Tasmota console parancsküldés |
| ⚙ **Config** | WiFi + MQTT + GPIO konfiguráció összeállítása és küldése |
| 📡 **MQTT** | Broker monitor – topic fa, payload viewer, üzenetnapló |
| 🔌 **Board** | Vizuális pin állapot térkép (élő, MQTT/Serial adatból) |

Részletes dokumentáció: [`docs/tasmota-manager.md`](../../docs/tasmota-manager.md)
