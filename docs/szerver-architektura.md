# Szerver architektúra

> **Státusz: Stack DÖNTVE** – 2026-05-19

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

### MQTT topic struktúra (javaslat)
```
smartblue/{device_id}/telemetry      # mérési adatok (eszköz → szerver)
smartblue/{device_id}/status         # heartbeat / online-offline
smartblue/{device_id}/config/get     # konfig kérés (eszköz → szerver)
smartblue/{device_id}/config/set     # konfig küldés (szerver → eszköz)
smartblue/{device_id}/alert          # riasztás az eszközről
```

### LWT (Last Will and Testament)
- Minden eszköz kapcsolódáskor beállít egy LWT üzenetet
- Ha a kapcsolat váratlanul megszakad, EMQX automatikusan publikálja:  
  `smartblue/{device_id}/status` → `{"online": false, "reason": "unexpected_disconnect"}`

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
        await client.subscribe("smartblue/#")
        app.state.mqtt = client
        asyncio.create_task(mqtt_listener(client))
        yield

async def mqtt_listener(client):
    async for message in client.messages:
        await handle_message(message)
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
  device_id: "esp32-001"
  device_type: "sensor_v1"
  location: "serbia-site-1"
fields:
  temperature: 23.5
  humidity: 61.2
  battery_pct: 87
  rssi: -72
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

### Folyamat

```
1. Felhasználó szerkeszti a konfig-ot (Web UI / API)
        │
        ▼
2. FastAPI elmenti PostgreSQL-be (új verzió, státusz: "pending")
        │
        ▼
3. FastAPI MQTT-n értesíti az eszközt:
   smartblue/{id}/config/set → {"version": 42, "action": "fetch"}
        │
        ▼
4. Eszköz HTTP GET-tel letölti:
   GET /api/v1/devices/{id}/config
        │
        ▼
5. Eszköz ACK-ol MQTT-n:
   smartblue/{id}/config/get → {"version": 42, "status": "applied"}
        │
        ▼
6. FastAPI frissíti a PostgreSQL-ben: státusz → "active"
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

## Nyitott kérdések

- [ ] Szükséges-e mobilalkalmazás, vagy web UI elegendő?
- [ ] Ki üzemelteti a szervert? (saját csapat)
- [ ] GDPR / adatvédelmi követelmények – EU-ban tároljunk vagy szerbiai szerveren?
- [ ] Szükséges-e real-time dashboard (Grafana), vagy csak riasztás/report?
- [ ] EMQX Rule Engine-t használjuk-e közvetlen InfluxDB íráshoz, vagy FastAPI kezelje?
- [ ] Milyen autentikáció legyen az eszközök és az EMQX között? (username/password, mTLS, JWT)
