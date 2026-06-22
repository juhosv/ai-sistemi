# Szerver architektúra

> **Státusz: Stack DÖNTVE** – 2026-05-19  
> **Megvalósítási fázis:** 1. fázis – adatgyűjtés, feldolgozás, dashboard → [`megvalositasi-terv.md`](megvalositasi-terv.md)

---

## 1. fázis scope (aktuális fókusz)

Az 1. fázisban a szerver **adatot gyűjt, tárol, feldolgoz és megjelenít** – szabályzás és eszközkonfiguráció később (2. fázis).

| Adattípus | Forrás | Tárolás |
|-----------|--------|---------|
| Szenzor / eszköz | MQTT (Tasmota) | InfluxDB |
| Felhasználói napló | REST API (feltöltés) | PostgreSQL |
| Külső (meteo stb.) | Scheduler + HTTP API | InfluxDB |
| Származtatott / stat | Batch job (aggregáció; később ML) | InfluxDB |

A későbbi **LLM chat** csak **adatmegjelenítő réteg** – nem helyettesíti a konfiguráció-kezelést vagy szabálymotort.

---

## Választott technológiai stack

| Réteg | Technológia | Szerepkör |
|-------|-------------|-----------|
| MQTT Broker | **EMQX** | Eszköz ↔ szerver üzenetközvetítés |
| Backend | **FastAPI** (Python) | REST API, üzleti logika, konfiguráció kezelés |
| MQTT kliens | **aiomqtt** (Python) | Async MQTT előfizetés a FastAPI-ban |
| Relációs DB | **PostgreSQL** | Eszközök, felhasználók, konfig, riasztások |
| Idősor DB | **InfluxDB** | Mérési adatok tárolása |

---

## Rendszer architektúra

```
[ESP32 eszközök]
      │
      │  MQTT (publish)
      ▼
  ┌─────────┐
  │  EMQX   │  ◄── MQTT Broker
  └────┬────┘
       │ subscribe (aiomqtt)
       ▼
  ┌──────────────────────────────────────────┐
  │           FastAPI alkalmazás             │
  │                                          │
  │  ┌────────────┐   ┌──────────────────┐  │
  │  │ MQTT Worker│   │   REST API       │  │
  │  │ (aiomqtt)  │   │  /api/v1/...     │  │
  │  └─────┬──────┘   └────────┬─────────┘  │
  │        │                   │            │
  │  ┌─────▼──────┐   ┌────────▼─────────┐  │
  │  │ Adat       │   │ Konfig / Auth /  │  │
  │  │ feldolgozás│   │ Riasztás logika  │  │
  │  └─────┬──────┘   └────────┬─────────┘  │
  └────────┼───────────────────┼────────────┘
           │                   │
     ┌─────▼──────┐    ┌───────▼──────┐
     │  InfluxDB  │    │  PostgreSQL  │
     │ (mérések)  │    │ (metaadatok) │
     └────────────┘    └──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Értesítési modul   │
                    │  Email / SMS / Push │
                    └─────────────────────┘
```

---

## EMQX – MQTT Broker

### Miért EMQX?
- Nagy teljesítmény: millió kapcsolat kezelése egyetlen csomóponton
- Beépített **web UI** (EMQX Dashboard) – eszközök monitorozása, topic böngésző
- Beépített **TLS/SSL** támogatás
- **Rule Engine** – adatok szűrése, transzformálása, továbbítása közvetlenül a brokerből
- **Webhook integráció** – EMQX-ből közvetlenül hívható FastAPI endpoint
- Docker-rel egyszerűen telepíthető

### EMQX Rule Engine lehetőség
Az EMQX Rule Engine képes közvetlenül InfluxDB-be írni MQTT üzenetekből – ez kiválthatja az aiomqtt→InfluxDB írást bizonyos esetekben (egyszerűsítés).

### MQTT topic struktúra – Tasmota konvenció

Az eszközök a **Tasmota firmware** MQTT struktúráját követik: `%prefix%/%topic%/<utasítás>`

```
cmnd/{device_topic}/POWER        # Vezérlés: Központ → Eszköz
cmnd/{device_topic}/TelePeriod   # Konfig parancs: Központ → Eszköz

stat/{device_topic}/RESULT       # JSON eredmény-visszajelzés: Eszköz → Központ
stat/{device_topic}/POWER        # Állapot visszajelzés: Eszköz → Központ

tele/{device_topic}/SENSOR       # Szenzoradatok (időközönként): Eszköz → Központ
tele/{device_topic}/STATE        # Eszköz állapot (WiFi, uptime): Eszköz → Központ
tele/{device_topic}/LWT          # Online / Offline jelzés: Broker küldi
```

→ Részletes topic dokumentáció: [`mqtt-protokoll.md`](mqtt-protokoll.md)

### LWT (Last Will and Testament)
- Minden eszköz kapcsolódáskor regisztrál egy LWT üzenetet az EMQX-ben
- Ha a kapcsolat váratlanul megszakad, az EMQX automatikusan publikálja:  
  `tele/{device_topic}/LWT` → `Offline`
- Újracsatlakozáskor az eszköz maga küldi:  
  `tele/{device_topic}/LWT` → `Online`

---

## FastAPI – Backend

### Miért FastAPI?
- **Async natív** – jól integrálható aiomqtt-vel (mindkettő asyncio alapú)
- Automatikus **OpenAPI / Swagger** dokumentáció
- **Pydantic** modellek – erős típusosság, automatikus validáció
- Gyors fejlesztés, Python ökoszisztéma (adatfeldolgozás, ml, stb.)

### Főbb API végpontok (tervezett)

| Endpoint | Metódus | Leírás |
|---------|---------|--------|
| `/api/v1/devices` | GET | Eszközök listája |
| `/api/v1/devices/{id}` | GET | Egy eszköz adatai, állapota |
| `/api/v1/devices/{id}/config` | GET/PUT | Konfiguráció lekérés / frissítés |
| `/api/v1/devices/{id}/telemetry` | GET | Mérési adatok (InfluxDB-ből) |
| `/api/v1/devices/{id}/alerts` | GET | Riasztások |
| `/api/v1/users` | GET/POST | Felhasználók |
| `/api/v1/notifications/test` | POST | Értesítés tesztelés |

### Belső modulstruktúra (javaslat)
```
app/
├── main.py                  # FastAPI app, startup/shutdown
├── mqtt/
│   ├── client.py            # aiomqtt connection manager
│   ├── handlers.py          # topic handler-ek (telemetry, status, stb.)
│   └── publisher.py         # szerver → eszköz üzenetküldés
├── api/
│   ├── devices.py
│   ├── config.py
│   ├── telemetry.py
│   └── alerts.py
├── db/
│   ├── postgres.py          # SQLAlchemy async
│   └── influx.py            # InfluxDB client
├── services/
│   ├── config_manager.py    # konfig verziókezelés
│   ├── health_monitor.py    # eszköz életjel figyelés
│   └── notifier.py          # email / SMS / push
└── models/                  # Pydantic + SQLAlchemy modellek
```

---

## aiomqtt – MQTT kliens a backendben

### Miért aiomqtt?
- **Teljesen async** (asyncio) – nem blokkolja a FastAPI event loop-ot
- Egyszerű, Pythonic API
- Paho-MQTT alapú, stabil
- Context manager alapú kapcsolatkezelés

### Indítási minta FastAPI-ban
```python
# main.py
from contextlib import asynccontextmanager
import aiomqtt

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiomqtt.Client("emqx-host") as client:
        # Tasmota topic struktúra szerinti feliratkozások
        await client.subscribe("tele/+/SENSOR")   # szenzoradatok
        await client.subscribe("tele/+/STATE")    # eszköz állapot
        await client.subscribe("tele/+/LWT")      # online/offline
        await client.subscribe("stat/+/#")        # parancs visszajelzések
        app.state.mqtt = client
        asyncio.create_task(mqtt_listener(client))
        yield

async def mqtt_listener(client):
    async for message in client.messages:
        await handle_message(message)

async def handle_message(message: aiomqtt.Message):
    parts = str(message.topic).split("/")
    prefix, device_topic, command = parts[0], parts[1], parts[2]
    match (prefix, command):
        case ("tele", "SENSOR"): await handle_sensor(device_topic, message.payload)
        case ("tele", "STATE"):  await handle_state(device_topic, message.payload)
        case ("tele", "LWT"):    await handle_lwt(device_topic, message.payload)
        case ("stat", _):        await handle_stat(device_topic, command, message.payload)
```

---

## PostgreSQL – Relációs adatbázis

### Tárolt adatok

| Tábla | Tartalom |
|-------|----------|
| `devices` | Eszköz ID, típus, helyszín, státusz, utolsó látás |
| `device_configs` | Konfig JSON, verzió, aktiválás időpontja |
| `users` | Felhasználók, értesítési beállítások |
| `alerts` | Riasztási eseménynapló |
| `notification_log` | Kiküldött értesítések naplója |

### ORM
- **SQLAlchemy 2.x** async módban (`asyncpg` driver)
- **Alembic** – adatbázis migráció kezelés

---

## InfluxDB – Idősor adatbázis

### Mérési adatok struktúrája

```
measurement: telemetry
tags:
  device_topic: "A1B2C3"       # MAC-alapú, firmware-agnosztikus azonosító
  device_type:  "sensor_v1"
  location:     "serbia-site-1"
fields:
  temperature: 23.5
  humidity:    61.2
  rssi:        -72
timestamp: 2026-05-19T16:00:00Z
```

### Adatmegőrzés (Retention Policy)
- Raw adatok: **90 nap** (teljes felbontás)
- Aggregált (óránkénti átlag): **1 év**
- Aggregált (napi átlag): **korlátlan**

### Vizualizáció
- **Grafana** csatlakoztatható InfluxDB-hez – dashboard nélküli időszakban is hasznos fejlesztési eszköz

---

## Konfiguráció kezelés és OTA

### Folyamat – Tasmota MQTT konfig küldéssel

```
1. Felhasználó szerkeszti a konfig-ot (Web UI / API)
        │
        ▼
2. FastAPI elmenti PostgreSQL-be (új verzió, státusz: "pending")
        │
        ▼
3. FastAPI egyenként elküldi a cmnd/ parancsokat MQTT-n:
   cmnd/{device_topic}/TelePeriod  → "60"
   cmnd/{device_topic}/PowerRetain → "1"
   cmnd/{device_topic}/<param>     → <érték>
        │
        ▼
4. Eszköz visszajelzést küld stat/ ágon:
   stat/{device_topic}/RESULT → {"TelePeriod":{"Every": 60}}
        │
        ▼
5. FastAPI fogadja a stat/ visszajelzést → konfig státusz → "active"
```

---

## Hibafigyelés (Device Health Monitoring)

### Rétegek

1. **EMQX LWT** – azonnali detektálás váratlan megszakadásnál
2. **Heartbeat timeout** – FastAPI figyeli az utolsó `status` üzenet időpontját
3. **Telemetry gap** – ha mérési adat nem érkezik a vártnál tovább → riasztás
4. **Konfig ACK timeout** – ha az eszköz nem nyugtázza a konfig-ot megadott időn belül

### Health Monitor service
- Háttérfeladat (FastAPI `asyncio.create_task`)
- Percenként végigmegy az eszközökön, ellenőrzi a `last_seen` mezőt
- Ha eszköz offline → riasztás létrehozása → értesítés küldése (deduplikáltan)

---

## Értesítési alrendszer

### Email
- Python: **aiosmtplib** (async SMTP)
- Szolgáltató: **Mailgun** vagy **SendGrid** (ajánlott) / saját SMTP
- HTML sablon (Jinja2)

### SMS
- **Infobip API** – Balkán régióban kiváló lefedettség, Szerbia elsődleges
- Python SDK: `infobip-api-python-client`

### Push (opcionális)
- **Telegram Bot** – gyors implementáció, nincs mobilapp szükséges
- FCM – csak ha mobilalkalmazás készül

---

## Deployment

### Docker Compose struktúra (javaslat)

```yaml
services:
  emqx:          # MQTT broker (port 1883, 8883 TLS, 18083 dashboard)
  fastapi:       # Backend alkalmazás
  postgres:      # Relációs adatbázis
  influxdb:      # Idősor adatbázis
  grafana:       # Vizualizáció (opcionális)
  nginx:         # Reverse proxy + TLS termination
```

### Hosting
- **VPS** (Hetzner Cloud CX22 vagy CX32) – pilot fázisra elegendő
- Minimum: 4 vCPU, 8 GB RAM, 80 GB SSD

---

## Döntések és nyitott kérdések

- [x] **Üzemeltetés:** Saját csapat – VPS + Docker Compose
- [ ] **Mobilalkalmazás:** Még nem döntött – web UI, PWA vagy natív app?
- [ ] **GDPR / adattárolás helye:** Még nem vizsgált – EU vs szerbiai szerver
- [ ] **Real-time dashboard:** Később döntünk – Grafana, egyedi UI, vagy csak riasztás
- [ ] **EMQX Rule Engine:** FastAPI vagy direkt EMQX → InfluxDB írás? – még nyitott
- [ ] **EMQX eszköz autentikáció:** username/password, mTLS vagy JWT? – még nyitott
