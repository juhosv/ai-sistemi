# MQTT Protokoll – Topic struktúra

> Az eszközök **Tasmota firmware** MQTT konvencióját követik.

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
| Relé bekapcsolás | `cmnd/nappali_lampa/POWER` | `ON` / `OFF` / `TOGGLE` |
| Aktuális állapot lekérés | `cmnd/nappali_lampa/POWER` | *(üres)* |
| Hálózati státusz lekérés | `cmnd/nappali_lampa/Status` | `5` |
| Telemetria időköz beállítás | `cmnd/nappali_lampa/TelePeriod` | `60` (másodperc) |

> **Megjegyzés:** Ha a parancs topicjára üres payloadot küldünk, az eszköz csak visszajelzi az aktuális állapotot, nem változtat rajta.

---

### 2. `stat/` – Állapot-visszajelzések (Eszköz → Központ)

Az eszköz ide publikálja a parancsok eredményét és megerősítéseit.

| Téma | Topic | Payload |
|------|-------|---------|
| Parancs megerősítés | `stat/nappali_lampa/POWER` | `ON` |
| JSON eredmény (bármilyen parancsra) | `stat/nappali_lampa/RESULT` | `{"POWER":"ON"}` |
| Státusz lekérés válasza | `stat/nappali_lampa/STATUS5` | `{"Status5":{"IPAddress":"192.168.1.50",...}}` |

---

### 3. `tele/` – Telemetria és szenzoradatok (Eszköz → Központ)

Az eszköz automatikusan, időközönként (alapértelmezetten **5 percenként**, `TelePeriod` paranccsal módosítható) vagy eseményvezérelten publikál ide.

#### Szenzoradatok – `tele/{topic}/SENSOR`
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
   Topic:   cmnd/nappali_lampa/POWER
   Payload: ON

2. Eszköz végrehajtja, majd publikál:
   Topic:   stat/nappali_lampa/RESULT  │ Payload: {"POWER":"ON"}
   Topic:   stat/nappali_lampa/POWER   │ Payload: ON

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
cmnd/{topic}/TelePeriod    → 60
cmnd/{topic}/PowerRetain   → 1
cmnd/{topic}/MqttHost      → szerver.example.com
cmnd/{topic}/MqttPort      → 1883
```

> A szerver a konfig verzióváltozáskor automatikusan elküldi a szükséges `cmnd/` üzeneteket MQTT-n.

---

## Csoportos vezérlés

Az összes Tasmota eszköz feliratkozik a `cmnd/tasmotas/#` topicra is (alapértelmezett GroupTopic). Ha ide publikálunk, az összes eszköz egyszerre hajtja végre:

```
cmnd/tasmotas/POWER  →  OFF   (összes eszköz kikapcsol)
```

> A GroupTopic felülírható eszközönként – érdemes projekt-specifikus csoportneveket használni, pl. `cmnd/smartblue_all/#`.

---

## FullTopic testreszabás

Ha az architektúra megkívánja, a topic sorrend megfordítható a Tasmota konzolból:

| Formátum | Példa |
|---------|-------|
| Alapértelmezett: `%prefix%/%topic%/` | `cmnd/nappali_lampa/POWER` |
| Megfordított: `%topic%/%prefix%/` | `nappali_lampa/cmnd/POWER` |

> **Projekt döntés szükséges:** Alapértelmezett Tasmota struktúrát tartjuk-e, vagy megfordítjuk?  
> Javaslat: **alapértelmezett megtartása** – egyszerűbb wildcard feliratkozás, jobb Tasmota kompatibilitás.

---

## InfluxDB adattárolás SENSOR üzenetből

A `tele/+/SENSOR` üzenet feldolgozásakor az adat InfluxDB-be kerül:

```
measurement: sensor_data
tags:
  device_topic: "nappali_lampa"
  sensor_type:  "BME280"
fields:
  temperature: 22.5
  humidity:    45.2
  pressure:    1013.7
timestamp:     (az üzenetben lévő "Time" mező, vagy fogadás ideje)
```

---

## Döntések

- [x] **FullTopic:** Alapértelmezett Tasmota sorrend marad: `cmnd/{topic}/...`
- [x] **TelePeriod:** 300 másodperc (5 perc) – alapértelmezett, eszközönként felülírható
- [x] **Eszköz `%topic%` neve:** MAC alapú (Tasmota alapértelmezett, pl. `tasmota_A1B2C3`) – változatlan MQTT azonosító
- [x] **Emberi név:** A szerver adatbázisban az eszközhöz rendelünk olvasható nevet (pl. „Hátsó udvar hőmérő"), a UI ezt jeleníti meg
- [ ] **GroupTopic:** Szükséges-e egyedi csoportnév (pl. `smartblue_all`)? – később döntünk
