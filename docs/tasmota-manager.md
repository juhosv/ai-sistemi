# SmartBlue Tasmota Device Manager

> **Elhelyezés:** `tools/tasmota-manager/`  
> **Indítás:** `python main.py`  
> **Python verzió:** 3.11+

---

## Áttekintés

A Tasmota Device Manager egy Python Textual TUI alkalmazás, amely ESP32 és ESP8266 eszközökre Tasmota firmware írását, konfigurálását és élő monitorozását teszi lehetővé.

Az alkalmazás 5 tabból áll:

| Tab | Funkció |
|-----|---------|
| ⚡ Flash | Firmware letöltés (GitHub) és égetés (esptool) |
| 🖥 Serial | Soros port monitor, Tasmota console parancsküldés |
| ⚙ Config | WiFi, MQTT, GPIO konfiguráció összeállítása és küldése |
| 📡 MQTT | Broker monitor, topic fa, payload viewer |
| 🔌 Board | Vizuális pin állapot térkép (élő) |

---

## Telepítés

```bash
cd tools/tasmota-manager
pip install -r requirements.txt
```

**Windows esetén** a CH340/CP2102 driverek telepítése szükséges az USB-soros adapter felismeréséhez.

---

## Indítás

```bash
python main.py
```

---

## Billentyűkötések

| Billentyű | Funkció |
|-----------|---------|
| F1–F5 | Tab váltás |
| Ctrl+S | Konfig profil mentése |
| Q | Kilépés |

---

## Tab 1 – Flash

1. Csatlakoztatd az ESP32/ESP8266 eszközt USB-n
2. Kattints a **↺ Frissítés** gombra – a port automatikusan megjelenik
3. Válaszd ki a firmware verziót:
   - `tasmota.bin` – ESP8266 standard build
   - `tasmota-lite.bin` – ESP8266 kisebb méret
   - `tasmota32.bin` – ESP32 standard build
4. **⬇ Letöltés** – letölti a legfrissebb verziót a GitHub Release-ből
5. **🔥 Égetés** – esptool-lal feltölti az eszközre (törlés opcionális)

---

## Tab 2 – Serial Monitor

- Soros port és baud ráta kiválasztás (alapértelmezett: 115200)
- **Csatlakozás** gomb → élő Tasmota soros kimenet
- Szín-kódolt sorok:
  - `MQT:` → cyan (MQTT esemény)
  - `WIF:` → kék/zöld (WiFi esemény)
  - `ERR:` → piros (hiba)
  - `RST:` → narancssárga (újraindítás)
- Parancs bevitel alul → Enter / ↵ Küldés gomb

Hasznos Tasmota parancsok:
```
Status          # eszköz állapot összefoglaló
Status 5        # hálózati info (IP, MAC)
Status 11       # GPIO állapotok
TelePeriod      # aktuális teleperiod lekérés
TelePeriod 60   # 60 másodperces teleperiod beállítás
Restart 1       # újraindítás
```

---

## Tab 3 – Konfiguráció

### Profil kezelés
- Mentett profilok betöltése / új profil mentése JSON fájlba (`profiles/` mappa)

### WiFi
- SSID1/Jelszó1 – elsődleges hálózat
- SSID2/Jelszó2 – tartalék hálózat (opcionális)

### MQTT
- Host, Port, User, Jelszó (üres = névtelen kapcsolat)
- Topic: az eszköz azonosítója (pl. `A1B2C3` → MAC-alapú)
- FullTopic: `%prefix%/%topic%/` (alapértelmezett Tasmota konvenció)

### GPIO kiosztás
A user **típust** választ (nem Tasmota belső kódot):

| Típus (amit lát) | Tasmota belső | MQTT üzenet |
|-----------------|---------------|-------------|
| Bemeneti érzékelő | Switch1/2/… | `{"Switch1": "ON"}` |
| Nyomógomb | Button1/2/… | `{"Button1": {"Action": "SINGLE"}}` |
| Relé / Kapcsoló kimenet | Relay1/2/… | `cmnd/…/POWER1 ON` |
| DHT22 hőmérséklet+pára | AM2301 | `{"AM2301": {"Temperature": 23.4, "Humidity": 61}}` |
| DS18B20 hőmérséklet | DS18x20 | `{"DS18B20": {"Temperature": 23.4}}` |
| I2C SCL / SDA | I2C SCL/SDA | – |

A sorszám (Switch**1**, Switch**2**) automatikusan kerül kiosztásra GPIO-sorrend alapján.

### Küldés
- **📡 Küldés soros porton** – soros port kapcsolaton keresztül (Serial tabban kell csatlakozni előtte)
- **📡 Küldés MQTT-n** – `cmnd/{topic}/...` topicokra publikálja a parancsokat (MQTT tabban kell csatlakozni előtte)

---

## Tab 4 – MQTT Monitor

1. Host/Port megadása, **Csatlakozás** gomb
2. Topic szűrő (alapértelmezett: `#` = minden)
3. Bal panel: topic fa – eszközönként, prefixenként rendezve, Online/Offline jelzéssel
4. Jobb panel: kiválasztott üzenet JSON payload pretty-print nézete
5. Alsó log: gördülő üzenetnapló időbélyeggel
6. Szűrő: prefix (tele/stat/cmnd) + eszköz topic

**Teszt eszközök:**
```
Host: broker.emqx.io  Port: 1883  Topic: #
Eszközök: vj_smart_sonoff_2026, kzs_smart_proba_2026
```

---

## Tab 5 – Board Monitor

Vizuális pin térkép az eszköz aktuális állapotával.

**Board típusok:** Wemos D1 Mini, NodeMCU v3, ESP32 DevKit V1, ESP32-S3 DevKit

**Adatforrás:**
- **MQTT mód** – automatikusan frissül `tele/.../STATE` és `tele/.../SENSOR` üzenetek alapján
- **Serial mód** – 5 másodpercenként kiküldi a `Status 11` és `Status 10` parancsokat

**Jelölések:**
- `■ ON` zölden – aktív, high pin
- `□ OFF` halványan – inaktív, low pin
- `⚠` – boot-érzékeny láb (GPIO0, GPIO2, GPIO15 az ESP8266-on)
- Sárga pont – ADC only bemenet
- Cyan pont – UART

---

## Konfig profil formátum (JSON)

```json
{
  "device_name": "Viktor teszt Sonoff",
  "topic": "vj_smart_sonoff_2026",
  "wifi": {
    "ssid1": "HomeNetwork",
    "password1": "...",
    "ssid2": "",
    "password2": ""
  },
  "mqtt": {
    "host": "broker.emqx.io",
    "port": 1883,
    "user": "",
    "password": "",
    "topic": "vj_smart_sonoff_2026",
    "full_topic": "%prefix%/%topic%/"
  },
  "tele_period": 300,
  "module_type": 18,
  "gpio": {
    "4": "switch",
    "5": "switch",
    "14": "relay"
  }
}
```

---

## Projekt összefüggés

Ez az eszköz az **eszközoldali provisioningot** segíti – az első firmware feltöltéstől a konfiguráció küldéséig. A konfigurált eszközök utána a SmartBlue szerver stack-hez csatlakoznak (EMQX broker → FastAPI → InfluxDB/PostgreSQL).

Kapcsolódó dokumentumok:
- [`szerver-architektura.md`](szerver-architektura.md) – szerver stack és MQTT topic struktúra
- [`mqtt-protokoll.md`](mqtt-protokoll.md) – Tasmota MQTT konvenciók
- [`hw-d1mini-tasmota.md`](hw-d1mini-tasmota.md) – Wemos D1 Mini hardver referencia
