---
name: Python Backend Terv
overview: A Python backend egyetlen asyncio folyamatban futtatja a FastAPI REST API-t és az aiomqtt MQTT klienst, megosztott event loop-on. Ez a minta bevett IoT backend architektúra, és az itt választott stack-re (FastAPI + aiomqtt) pontosan illeszkedik.
todos:
  - id: struktura
    content: Backend könyvtárstruktúra és requirements.txt létrehozása
    status: pending
  - id: core-config
    content: core/config.py – pydantic-settings alapú konfiguráció (.env)
    status: pending
  - id: db-postgres
    content: db/postgres.py – SQLAlchemy async engine + session factory + ORM modellek
    status: pending
  - id: db-influx
    content: db/influx.py – InfluxDB async write/query wrapperek
    status: pending
  - id: mqtt-loop
    content: mqtt/loop.py – reconnect loop + feliratkozások
    status: pending
  - id: mqtt-dispatcher
    content: mqtt/dispatcher.py + handlers/ – topic routing és handler-ek
    status: pending
  - id: mqtt-publisher
    content: mqtt/publisher.py – cmnd/ publikálás + Depends() dependency
    status: pending
  - id: api-routes
    content: api/v1/ – devices, telemetry, config, alerts route-ok
    status: pending
  - id: services
    content: services/ – device, telemetry, config, health_monitor, notifier
    status: pending
  - id: main
    content: main.py – FastAPI app + lifespan (MQTT task + health monitor task)
    status: pending
  - id: docker
    content: Dockerfile + docker-compose.yml (emqx, fastapi, postgres, influxdb)
    status: pending
isProject: false
---


# Python Backend Architektúra Terv

## Miért jó ez a választás?

FastAPI és aiomqtt mindkettő `asyncio`-alapú – ugyanazon az event loop-on futnak, nem blokkolják egymást. Az MQTT listener egy háttér-`Task`, a FastAPI route-ok párhuzamosan futhatnak mellette. Ez egyszerű, jól tesztelhető, és a pilot fázishoz tökéletesen elegendő.

## Adatfolyam

```mermaid
flowchart LR
    subgraph devices [Eszközök]
        ESP32
    end

    subgraph broker [EMQX Broker]
        MQTT
    end

    subgraph backend [FastAPI folyamat - egyetlen asyncio event loop]
        mqttLoop["mqtt/loop.py\n(reconnect loop)"]
        dispatcher["mqtt/dispatcher.py\n(topic routing)"]
        publisher["mqtt/publisher.py\n(cmnd/ küldés)"]
        
        subgraph handlers [mqtt/handlers/]
            sensorH["sensor.py\ntele/+/SENSOR"]
            stateH["state.py\ntele/+/STATE"]
            lwtH["lwt.py\ntele/+/LWT"]
            statH["stat.py\nstat/+/#"]
        end

        subgraph api [api/v1/]
            devicesAPI["devices.py"]
            telemetryAPI["telemetry.py"]
            configAPI["config.py"]
            alertsAPI["alerts.py"]
        end

        subgraph services [services/]
            deviceSvc["device_service.py"]
            telemetrySvc["telemetry_service.py"]
            configSvc["config_service.py"]
            healthMon["health_monitor.py\n(asyncio Task)"]
            notifier["notifier.py"]
        end
    end

    subgraph dbs [Adatbázisok]
        PG[(PostgreSQL)]
        Influx[(InfluxDB)]
    end

    subgraph ui [Kliens]
        UI[Web UI]
    end

    ESP32 -->|"tele/ stat/"| MQTT
    MQTT -->|subscribe| mqttLoop
    mqttLoop --> dispatcher
    dispatcher --> sensorH & stateH & lwtH & statH
    sensorH --> telemetrySvc --> Influx
    stateH & lwtH & statH --> deviceSvc --> PG
    healthMon -->|"last_seen check"| PG
    healthMon --> notifier

    UI -->|"REST GET/PUT"| api
    api --> services
    configAPI --> configSvc --> publisher
    publisher -->|"cmnd/"| MQTT
    telemetryAPI --> telemetrySvc --> Influx
    devicesAPI --> deviceSvc --> PG
```

## Könyvtárstruktúra

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + lifespan (MQTT task + health task indítás)
│   ├── core/
│   │   └── config.py            # pydantic-settings: MQTT host, DB URL, stb. (.env-ből)
│   ├── mqtt/
│   │   ├── loop.py              # Reconnect loop (while True + MqttError catch)
│   │   ├── dispatcher.py        # topic split → match/case → handler hívás
│   │   ├── publisher.py         # app.state.mqtt_client-en keresztül cmnd/ publikálás
│   │   └── handlers/
│   │       ├── sensor.py        # tele/+/SENSOR → InfluxDB
│   │       ├── state.py         # tele/+/STATE → PostgreSQL last_seen, wifi_rssi
│   │       ├── lwt.py           # tele/+/LWT → PostgreSQL online/offline státusz
│   │       └── stat.py          # stat/+/# → konfig ACK feldolgozás
│   ├── api/v1/
│   │   ├── router.py            # APIRouter összefogó
│   │   ├── devices.py           # GET /devices, GET /devices/{id}
│   │   ├── telemetry.py         # GET /devices/{id}/telemetry (InfluxDB)
│   │   ├── config.py            # GET/PUT /devices/{id}/config
│   │   └── alerts.py            # GET /devices/{id}/alerts
│   ├── db/
│   │   ├── postgres.py          # SQLAlchemy async_engine + AsyncSession factory
│   │   ├── influx.py            # InfluxDB write_api + query_api wrapperek
│   │   └── models/              # SQLAlchemy ORM modellek
│   ├── schemas/                 # Pydantic request/response modellek
│   ├── services/
│   │   ├── device_service.py    # Eszköz CRUD, státusz frissítés
│   │   ├── telemetry_service.py # InfluxDB írás/olvasás
│   │   ├── config_service.py    # Konfig verziókezelés + MQTT cmnd/ küldés
│   │   ├── health_monitor.py    # Háttér asyncio.Task: last_seen poll + riasztás
│   │   └── notifier.py          # Email (aiosmtplib) + SMS (Infobip)
│   └── dependencies.py          # Depends(get_session), Depends(get_mqtt_publisher)
├── alembic/                     # DB migrációk
├── tests/
├── .env.example
├── Dockerfile
└── requirements.txt
```

## Kulcsminták

### 1. Lifespan – minden háttérfeladat indítása (`main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    task_mqtt = asyncio.create_task(mqtt_loop(app))
    task_health = asyncio.create_task(health_monitor_loop())
    yield
    task_mqtt.cancel()
    task_health.cancel()
```

### 2. Robusztus MQTT reconnect loop (`mqtt/loop.py`)

```python
async def mqtt_loop(app: FastAPI):
    while True:
        try:
            async with aiomqtt.Client(settings.MQTT_HOST) as client:
                await client.subscribe("tele/+/SENSOR")
                await client.subscribe("tele/+/STATE")
                await client.subscribe("tele/+/LWT")
                await client.subscribe("stat/+/#")
                app.state.mqtt_client = client      # publisher számára
                async for message in client.messages:
                    await dispatch(message)
        except aiomqtt.MqttError:
            app.state.mqtt_client = None
            await asyncio.sleep(5)                  # reconnect várakozás
```

### 3. DB session – kétféle kontextus

- **API route-ban** (request context): `Depends(get_session)` – FastAPI kezeli
- **MQTT handler-ben** (nincs request context): `async with async_session() as db:`

### 4. Publisher hozzáférése API route-ból

```python
# dependencies.py
def get_mqtt_publisher(request: Request) -> MqttPublisher:
    return MqttPublisher(client=request.app.state.mqtt_client)

# config.py route
@router.put("/{id}/config")
async def update_config(id: str, publisher=Depends(get_mqtt_publisher), ...):
    await config_service.apply(id, config, publisher)
```

## Technológiai függőségek (`requirements.txt`)

- `fastapi`, `uvicorn[standard]`
- `aiomqtt`
- `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- `influxdb-client[async]`
- `pydantic-settings`
- `aiosmtplib`, `jinja2` (email)
- `httpx` (Infobip SMS API)

## Ami még nyitott (nem blokkolja az implementációt)

- EMQX eszköz autentikáció módja (user/pass egyelőre elegendő)
- Dashboard / UI technológia
- EMQX Rule Engine vs FastAPI → InfluxDB (eldönthető implementáció közben)
