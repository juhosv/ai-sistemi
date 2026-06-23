# MQTT Protokoll – Topic struktúra

> Az eszközök jelenleg **Tasmota firmware** MQTT konvencióját követik.  
> ESPHome irány esetén más topic struktúra szükséges → lásd [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md).

---

## Alapstruktúra

```
%prefix%/%topic%/<utasítás>
```

| Elem | Leírás | Példa |
|------|--------|-------|
| `%prefix%` | Az üzenet iránya és funkciója | `cmnd`, `stat`, `tele` |
| `%topic%` | Az eszköz egyedi neve | `nappali_lampa`, `tasmota_A1B2C3` |
| `<utasítás>` | A konkrét parancs vagy adat típusa | `POWER`, `SENSOR`, `STATE` |

---

## A három fő prefix

### 1. `cmnd/` – Parancsok (Központ → Eszköz)

A szerver ide publikálja a vezérlési parancsokat és lekérdezéseket. Az eszköz folyamatosan fel van iratkozva a saját `cmnd/` topicjaira.

| Példa | Topic | Payload |
|-------|-------|---------|
| Relé bekapcsolás | `cmnd/A1B2C3/POWER` | `ON` / `OFF` / `TOGGLE` |
| Aktuális állapot lekérés | `cmnd/A1B2C3/POWER` | *(üres)* |
| Hálózati státusz lekérés | `cmnd/A1B2C3/Status` | `5` |
| Telemetria időköz beállítás | `cmnd/A1B2C3/TelePeriod` | `60` (másodperc) |

> **Megjegyzés:** Ha a parancs topicjára üres payloadot küldünk, az eszköz csak visszajelzi az aktuális állapotot, nem változtat rajta.

---

### 2. `stat/` – Állapot-visszajelzések (Eszköz → Központ)

Az eszköz ide publikálja a parancsok eredményét és megerősítéseit.

| Téma | Topic | Payload |
|------|-------|---------|
| Parancs megerősítés | `stat/A1B2C3/POWER` | `ON` |
| JSON eredmény (bármilyen parancsra) | `stat/A1B2C3/RESULT` | `{"POWER":"ON"}` |
| Státusz lekérés válasza | `stat/A1B2C3/STATUS5` | `{"Status5":{"IPAddress":"192.168.1.50",...}}` |

---

### 3. `tele/` – Telemetria és szenzoradatok (Eszköz → Központ)

Az eszköz automatikusan, időközönként (alapértelmezetten **5 percenként**, `TelePeriod` paranccsal módosítható) vagy eseményvezérelten publikál ide.

#### Szenzoradatok – `tele/{topic}/SENSOR`

> **Fontos:** A SENSOR üzenet küldési viselkedése **szenzortípusonként eltér:**
> - **Fizikai szenzor (DHT22, BME280 stb.):** periodikusan, `TelePeriod` szerint (alapból 5 percenként)
> - **Switch bemenet (gomb, PIR, reed relé):** csak **állapotváltáskor** (edge-triggered), nem periodikusan

Fizikai szenzor (periodikus):
```json
{
  "Time": "2026-05-19T17:30:00",
  "BME280": {
    "Temperature": 22.5,
    "Humidity": 45.2,
    "Pressure": 1013.7
  },
  "TempUnit": "C"
}
```

Switch bemenet (csak váltáskor – tesztből megerősítve 2026-05-27):
```json
{"Time": "2026-05-27T21:56:51", "Switch1": "ON"}
{"Time": "2026-05-27T21:56:53", "Switch1": "OFF"}
```

#### Eszköz állapota – `tele/{topic}/STATE`
```json
{
  "Time": "2026-05-19T17:30:00",
  "Uptime": "1T02:30:00",
  "UptimeSec": 95400,
  "Heap": 26,
  "SleepMode": "Dynamic",
  "Sleep": 50,
  "LoadAvg": 19,
  "MqttCount": 1,
  "POWER": "ON",
  "Wifi": {
    "AP": 1,
    "SSId": "MyWifi",
    "BSSId": "AA:BB:CC:DD:EE:FF",
    "Channel": 6,
    "RSSI": 74,
    "Signal": -63,
    "LinkCount": 1,
    "Downtime": "0T00:00:03"
  }
}
```

#### Elérhetőség (LWT) – `tele/{topic}/LWT`

| Esemény | Payload |
|---------|---------|
| Eszköz csatlakozik | `Online` |
| Eszköz megszakad (MQTT broker tárolja és elküldi) | `Offline` |

> Az LWT üzenetet a **broker (EMQX)** tárolja és automatikusan kiküldi, ha az eszköz kapcsolata váratlanul megszakad – nem az eszköz küldi!

---

## Teljes kétirányú kommunikáció – példa

```
Felhasználó vezérli a lámpát a webes felületen:

1. Szerver publikál:
   Topic:   cmnd/A1B2C3/POWER
   Payload: ON

2. Eszköz végrehajtja, majd publikál:
   Topic:   stat/A1B2C3/RESULT  │ Payload: {"POWER":"ON"}
   Topic:   stat/A1B2C3/POWER   │ Payload: ON

3. Szerver fogadja a stat/ visszajelzést → frissíti az eszköz állapotát az adatbázisban
```

---

## FastAPI + aiomqtt feliratkozási stratégia

A backend az EMQX-en keresztül az alábbi wildcard topicokra iratkozik fel:

```python
# Összes eszköz telemetriája
await client.subscribe("tele/+/SENSOR")
await client.subscribe("tele/+/STATE")
await client.subscribe("tele/+/LWT")

# Összes eszköz állapot-visszajelzése
await client.subscribe("stat/+/#")
```

### Topic handler struktúra

```python
async def handle_message(message: aiomqtt.Message):
    topic_parts = str(message.topic).split("/")
    prefix = topic_parts[0]        # cmnd / stat / tele
    device_topic = topic_parts[1]  # eszköz neve
    command = topic_parts[2]       # SENSOR, STATE, LWT, POWER, stb.

    match (prefix, command):
        case ("tele", "SENSOR"):
            await handle_sensor_data(device_topic, message.payload)
        case ("tele", "STATE"):
            await handle_device_state(device_topic, message.payload)
        case ("tele", "LWT"):
            await handle_lwt(device_topic, message.payload)
        case ("stat", "RESULT"):
            await handle_command_result(device_topic, message.payload)
```

---

## Konfiguráció küldése eszköznek

A Tasmota konfig parancsokat egyenként `cmnd/` ágon kell elküldeni. Több paraméter esetén egymás után:

```
cmnd/A1B2C3/TelePeriod    → 60
cmnd/A1B2C3/PowerRetain   → 1
cmnd/A1B2C3/MqttHost      → szerver.example.com
cmnd/A1B2C3/MqttPort      → 1883
```

> A szerver a konfig verzióváltozáskor automatikusan elküldi a szükséges `cmnd/` üzeneteket MQTT-n.

---

## Csoportos vezérlés

Az összes Tasmota eszköz feliratkozik a `cmnd/tasmotas/#` topicra is (alapértelmezett GroupTopic). Ha ide publikálunk, az összes eszköz egyszerre hajtja végre:

```
cmnd/tasmotas/POWER  →  OFF   (összes Tasmota eszköz kikapcsol)
```

> A GroupTopic felülírható eszközönként – érdemes projekt-specifikus csoportneveket használni, pl. `cmnd/smartblue_all/#`.

---

## FullTopic testreszabás

A SmartBlue projekt csoportos topic hierarchiát alkalmaz, ahol a FullTopic tartalmazza a user és régió azonosítókat:

| Formátum | Példa |
|---------|-------|
| Alapértelmezett Tasmota: `%prefix%/%topic%/` | `cmnd/A1B2C3/POWER` |
| SmartBlue csoportos: `{user}/{region}/%topic%/%prefix%/` | `juhosv/hu_eszak/A1B2C3/cmnd/POWER` |

**Topic hierarchia sorrend:** `user_id / region_id / %topic% / %prefix%`

- Az eszközre küldött FullTopic beállítás: `juhosv/hu_eszak/%topic%/%prefix%/`
- MQTT feliratkozás egy eszközre: `juhosv/hu_eszak/A1B2C3/#`
- MQTT feliratkozás egy user összes eszközére: `juhosv/hu_eszak/#`

> **Sorrend indoklás:** A user_id kerül előre, mert az elsődleges szervezési szint a felhasználó; a régió másodlagos (földrajzi/szervezeti alcsoportok).

---

## InfluxDB adattárolás SENSOR üzenetből

A `tele/+/SENSOR` üzenet feldolgozásakor az adat InfluxDB-be kerül:

```
measurement: sensor_data
tags:
  device_topic: "A1B2C3"
  sensor_type:  "BME280"
fields:
  temperature: 22.5
  humidity:    45.2
  pressure:    1013.7
timestamp:     (az üzenetben lévő "Time" mező, vagy fogadás ideje)
```

---

## Döntések

- [x] **FullTopic:** SmartBlue csoportos hierarchia: `{user}/{region}/%topic%/%prefix%/` – pl. `juhosv/hu_eszak/A1B2C3/tele/SENSOR`
- [x] **TelePeriod:** 300 másodperc (5 perc) – alapértelmezett, eszközönként felülírható
- [x] **Eszköz `%topic%` neve:** MAC-alapú, **firmware-előtag nélkül** – csak a 6 hex karakteres MAC-suffix (pl. `A1B2C3`)
  - Tasmota alapértelmezettje `tasmota_A1B2C3` – ezt felül kell írni provisioning során: `Topic A1B2C3`
  - Firmware-agnosztikus: ha később nem Tasmota alapú eszköz kerül be, ugyanolyan formátumú azonosítót kap
- [x] **Emberi név:** A szerver adatbázisban az eszközhöz rendelünk olvasható nevet (pl. „Hátsó udvar hőmérő"), a UI ezt jeleníti meg
- [ ] **GroupTopic:** Szükséges-e egyedi csoportnév (pl. `smartblue_all`)? – később döntünk
