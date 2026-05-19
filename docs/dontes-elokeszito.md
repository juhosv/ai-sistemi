# Döntés-előkészítő összefoglaló

## Státusz: Részlegesen döntve – 2026-05-19

Ez a dokumentum összefoglalja a nyitott döntési pontokat és a javasolt következő lépéseket.

---

## Döntési mátrix – kommunikáció

| Kérdés | Opció A | Opció B | Opció C |
|--------|---------|---------|---------|
| Kommunikáció | WiFi only | GSM 4G only | Hibrid (WiFi + GSM) |
| Hardverköltség | Alacsony | Magas | Legmagasabb |
| Üzemeltetési rugalmasság | Alacsony | Magas | Maximális |
| Terepi alkalmasság | Korlátozott | Kiváló | Kiváló |
| Fejlesztési komplexitás | Alacsony | Közepes | Magas |
| **Pilot fázis javasolt?** | Csak beltéri helyszínen | **Igen** | Következő fázisban |

---

## Szerver backend – DÖNTVE ✓

| Komponens | Döntés | Megjegyzés |
|-----------|--------|------------|
| MQTT Broker | **EMQX** | Dashboard, Rule Engine, TLS, skálázható |
| Backend framework | **FastAPI** (Python) | Async, Pydantic, OpenAPI |
| MQTT kliens (backend) | **aiomqtt** | Async, asyncio-kompatibilis |
| Relációs adatbázis | **PostgreSQL** | Eszközök, konfig, riasztások, felhasználók |
| Idősor adatbázis | **InfluxDB** | Mérési adatok, retention policy-val |

→ Részletes architektúra: [`szerver-architektura.md`](szerver-architektura.md)

---

## Döntési mátrix – értesítések

| Csatorna | Megvalósíthatóság | Szerbia lefedettség | Prioritás |
|---------|-------------------|---------------------|-----------|
| Email | Egyszerű | Teljes | Kötelező |
| SMS (Infobip) | Közepes | Kiváló | Javasolt |
| Push (Telegram bot) | Könnyű | Teljes | Opcionális (gyors) |
| Push (FCM) | Nehezebb | Teljes | Csak ha van mobilapp |

---

## Összesített stack – pilot fázis

```
Eszköz:       ESP32 WiFi (Tasmota firmware)                    [döntve]
Kommunikáció: WiFi – beltéri helyszínek, garantált lefedettség [döntve]
GSM (2. fáz): 1NCE IoT SIM kártyák                            [döntve]
Protokoll:    MQTT – Tasmota konvenció (cmnd / stat / tele)    [döntve]
Topic névkon: MAC-suffix only (pl. A1B2C3), firmware-agnosztikus + emberi név az adatbázisban   [döntve]
TelePeriod:   300 mp (5 perc)                                  [döntve]
MQTT Broker:  EMQX (alapért. FullTopic struktúra)              [döntve]
Backend:      Python / FastAPI + aiomqtt                       [döntve]
Relációs DB:  PostgreSQL (SQLAlchemy async + Alembic)          [döntve]
Idősor DB:    InfluxDB                                         [döntve]
Üzemeltetés: Saját csapat – VPS + Docker Compose              [döntve]
Értesítés:    Email (kötelező) + SMS (javasolt)                [nyitott]
Dashboard:    Még nem döntött                                  [nyitott]
Mobilapp:     Még nem döntött                                  [nyitott]
GDPR:         Még nem vizsgált                                 [nyitott]
EMQX auth:    Még nem döntött                                  [nyitott]
```

---

## Következő lépések

- [x] **Helyszín felmérés** – beltéri, WiFi garantált
- [x] **SIM kártya stratégia** – 1NCE IoT SIM kártyák (következő fázishoz)
- [ ] **Eszközcsalád pontosítása** – hőmérséklet/páratartalom, relé, mozgásérzékelő ismert; további típusok nyitottak
- [x] **Csapat technológiai ismerete** – Python/FastAPI stack kiválasztva
- [ ] **MVP scope meghatározása** – mi kell az első pilot induláshoz minimálisan
- [ ] **GDPR / adatvédelem** – szerbiai vs EU adattárolás jogi vizsgálata szükséges
- [ ] **EMQX autentikáció** – eszköz azonosítási módszer kiválasztása
- [ ] **Mobilalkalmazás döntés** – web UI, PWA vagy natív?
- [ ] **Dashboard döntés** – Grafana, egyedi, vagy csak riasztás?

---

## Nyitott kérdések összesítve

### Eszköz / kommunikáció
- Beltéri vagy kültéri telepítések?
- Van WiFi infrastruktúra a helyszíneken?
- Akkumulátoros vagy hálózati táplálás?
- NB-IoT / Cat-M lefedettség Szerbiában?

### Szerver / adatok
- Várható eszközszám pilot fázisban?
- Szükséges mobilalkalmazás?
- Ki üzemelteti a szervert?
- Real-time dashboard szükséges?

### Üzleti / projekt
- Mekkora a fejlesztési csapat?
- Mi a pilot fázis sikerkritériuma?
- Mikor kell az első pilot indulnia?
