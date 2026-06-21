# Döntés-előkészítő összefoglaló

## Státusz: Részlegesen döntve – 2026-05-19

Ez a dokumentum összefoglalja a nyitott döntési pontokat és a javasolt következő lépéseket.

---

## Döntési mátrix – kommunikáció

| Kérdés | WiFi only | WiFi + ext. antenna | GSM 4G | LoRa |
|--------|-----------|---------------------|--------|------|
| Hardverköltség | Alacsony | Alacsony | Magas | Közepes |
| Üzemeltetési rugalmasság | Alacsony | Alacsony | Magas | Közepes |
| Terepi alkalmasság | Korlátozott | Korlátozott | Kiváló | Kiváló (saját GW) |
| Fejlesztési komplexitás | Alacsony | Alacsony | Közepes | Magas |
| Sávszélesség / OTA | Nagy | Nagy | Közepes | Nagyon korlátozott |
| **Pilot fázis javasolt?** | **Igen (beltéri)** | Ha gyenge WiFi jel | Következő fázisban | Feltérképezendő |

> Részletes elemzés: [kommunikacio.md](kommunikacio.md) – WiFi, külső antenna, GSM, LoRa összehasonlítás

--------|---------|---------|---------|
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
- [ ] **Eszközcsalád pontosítása** – hőmérséklet/páratartalom, relé, mozgásérzékelő ismert; ventilátor + gépmoniror új termékként szóba jött
- [x] **Csapat technológiai ismerete** – Python/FastAPI stack kiválasztva
- [ ] **MVP scope meghatározása** – mi kell az első pilot induláshoz minimálisan
- [ ] **GDPR / adatvédelem** – szerbiai vs EU adattárolás jogi vizsgálata szükséges
- [ ] **EMQX autentikáció** – eszköz azonosítási módszer kiválasztása
- [ ] **Mobilalkalmazás / provisioning döntés** – web UI, PWA vagy natív? Bluetooth/NFC alapú telepítési segéd vizsgálva (lásd `termek-otletek.md` – Bluetooth/NFC provisioning fejezet): rövidtávon Tasmota AP mód elegendő; középtávon webes konfigurátor + QR/NFC tag javasolt
- [ ] **Dashboard döntés** – Grafana, egyedi, vagy csak riasztás?
- [ ] **GitHub migráció** – projekt repo létrehozása, Obsidian Git plugin, csapat hozzáférés (Sogi, Robi, Alfréd)
- [ ] **Projektmenedzsment eszköz** – kiválasztás és beállítás
- [ ] **Robi szervere** – Bálint megvizsgálja, megfelelő-e a SmartBlue stack-nek
- [ ] **Fejlesztési ötletek gyűjtése** – Robi és Alfréd inputja a prioritásokhoz
- [ ] **Otthoni adatgyűjtés (Viktor)** – minél több eszköz/szenzor üzembe helyezése, mintaadatok gyűjtése az AI agent kísérletekhez
- [ ] **Szerver vásárlás** – Zsolti intézi a produkciós szerver beszerzését
- [ ] **Honlap elkészítése** – Bálint összeállítja; tartalmazza a korábbi munkák leírását is
- [ ] **Domain név kiválasztása** – `.rs` végződésű domain
- [ ] **Háromfázisú teljesítménymérő minta** – Zsolti áramkör → Zöldinél beüzemelés
- [ ] **Mezőgazdasági pilot** – Ervinnel; Gilvázi Istvánnál fólia sátras minta projekt lehetőség
- [ ] **AI agent (Hermes) multi-tenant architektúra** – felhasználónkénti adatelkülönítés megoldása
- [ ] **AI paraméterezés + Node-RED** – eszközparaméterek AI-val állítása; multi-user kezelés Node-RED-ben

## Teszt fázis – státusz

- [x] Tasmota telepítési leírás elkészült → Sogi megkapta
- [x] Teszt szerver kész (Bálint) – email értesítés D1 Mini üzenetre
- [x] Sogi megkapta az MQTT beállításokat
- [x] **End-to-end teszt sikeres** (2026-05-27): Sogi eszköze (`kzs_smart_proba_2026`) MQTT üzenetet küld a publikus brókernek
- [ ] Email értesítés Soginak Switch eseménykor (`zsoltorigo@gmail.com`)
- [ ] PIR szenzor éles teszt

### Tanulság a tesztből – Switch SENSOR viselkedés

A Tasmota Switch bemenet **csak állapotváltáskor** küld `tele/.../SENSOR` üzenetet, nem periodikusan:
```json
tele/kzs_smart_proba_2026/SENSOR → {"Time":"...","Switch1":"ON"}   ← váltáskor
tele/kzs_smart_proba_2026/SENSOR → {"Time":"...","Switch1":"OFF"}  ← visszaváltáskor
```
Ez **edge-triggered** logika – a szervernek ezt figyelembe kell vennie a feldolgozásnál.

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
- Milyen `.rs` domain név legyen?
- Honlap tartalma és struktúra – milyen korábbi munkákat emeljünk ki?

### AI / adatfeldolgozás
- Hermes Agent self-hosted vagy felhő?
- Hogyan biztosítjuk, hogy az agent csak az adott user adatait látja?
- Node-RED: külön instance user-enként, vagy tenant-szűrés egy instance-ben?
- Milyen LLM backend (lokális vs. API)?
- Milyen meteorológiai API-k használhatók Szerbiában (mezőgazdasági pilot)?
