# Döntés-előkészítő összefoglaló

## Státusz: Részlegesen döntve – 2026-05-19 (firmware felülvizsgálat: 2026-06-23)

Ez a dokumentum összefoglalja a nyitott döntési pontokat és a javasolt következő lépéseket.

---

## Firmware – FELÜLVIZSGÁLAT ALATT ⚠

| | Tasmota (eddigi) | ESPHome (valószínű irány) |
|---|------------------|---------------------------|
| Státusz | Pilot teszt sikeres (2026-05-27) | Döntés előkészítés (2026-06-23) |
| Konfiguráció | Eszközönkénti WebUI | Központi YAML + OTA |
| Flotta / multi-tenant | Nehézkes | Packages + saját backend provisioning |
| MQTT | `cmnd/stat/tele` – döntve | Saját topic séma – **definiálandó** |
| HA szükséges? | Nem | Nem (MQTT mód) |

→ Részletes elemzés, összehasonlítás, választott architektúra: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md)

**Előzetes javaslat:** ESPHome + **ThingsBoard CE** (ön-hosztolt, ingyenes licenc). A Tasmota teszt és tooling megmarad referenciának.

→ Szerver részletek: [`thingsboard-dontes.md`](thingsboard-dontes.md)

---

## Szerver platform – FELÜLVIZSGÁLAT ALATT ⚠

| | FastAPI stack (eddigi) | ThingsBoard (valószínű irány) |
|---|------------------------|-------------------------------|
| Státusz | Döntve 2026-05-19 | Döntés előkészítés 2026-06-23 |
| MQTT | EMQX külön | Beépített vagy EMQX |
| Backend | FastAPI + aiomqtt | ThingsBoard beépített |
| Dashboard | Grafana + saját web UI | **TB vizuális dashboard** |
| Multi-tenant | Saját fejlesztés | **Customers, Assets, Roles** |
| FOTA | Saját fejlesztés | **Beépített OTA** |
| Licenc | – | **CE ingyenes** (Apache 2.0) |

→ Részletes elemzés: [`thingsboard-dontes.md`](thingsboard-dontes.md)

**Előzetes javaslat:** ThingsBoard **CE** + ESPHome (MQTT), saját VPS (~5–15 EUR/hó). A korábbi FastAPI/InfluxDB stack felülvizsgálat alatt.

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

## Szerver backend – FELÜLVIZSGÁLAT ALATT ⚠

| Komponens | Eddigi döntés (2026-05-19) | ThingsBoard irány (2026-06-23) |
|-----------|----------------------------|--------------------------------|
| IoT platform | FastAPI (saját) | **ThingsBoard CE** (ingyenes, ön-hosztolt) |
| MQTT Broker | EMQX | TB beépített **vagy** EMQX – döntendő |
| Backend framework | FastAPI + aiomqtt | TB beépített (+ opcionális microservice) |
| Adattárolás | PostgreSQL + InfluxDB | TB saját DB (PostgreSQL/Cassandra) |
| Dashboard | Grafana + web UI | **TB dashboard** |

→ Korábbi architektúra: [`szerver-architektura.md`](szerver-architektura.md)  
→ Új döntési folyamat: [`thingsboard-dontes.md`](thingsboard-dontes.md)  
→ **Megvalósítási lépések:** [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)

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
Eszköz:       ESP32 WiFi (Tasmota → ESPHome?)                  [felülvizsgálat]
Kommunikáció: WiFi – beltéri helyszínek, garantált lefedettség [döntve]
GSM (2. fáz): 1NCE IoT SIM – **4G router + ESPHome** vagy TinyGSM FW  [döntendő]
Protokoll:    MQTT – Tasmota konvenció (cmnd / stat / tele)    [döntve; ESPHome esetén új séma]
Topic névkon: MAC-suffix only (pl. A1B2C3), firmware-agnosztikus + emberi név az adatbázisban   [döntve]
TelePeriod:   300 mp (5 perc)                                  [döntve]
MQTT Broker:  EMQX vagy ThingsBoard beépített                   [felülvizsgálat]
Backend:      ThingsBoard (volt: FastAPI + aiomqtt)             [felülvizsgálat]
Adattárolás:  ThingsBoard DB (volt: PostgreSQL + InfluxDB)     [felülvizsgálat]
Üzemeltetés: Saját csapat – VPS + Docker Compose (TB CE)     [előzetes]
Megvalósítás: 1. fázis – adatgyűjtés + dashboard               [döntve 2026-06-21]
Értesítés:    Email (kötelező) + SMS (javasolt)                [2. fázis]
Dashboard:    ThingsBoard (volt: Grafana + web UI)              [felülvizsgálat]
Mobilapp:     Még nem döntött                                  [nyitott]
GDPR:         Még nem vizsgált                                 [nyitott]
EMQX auth:    Még nem döntött                                  [nyitott]
LLM chat:     Később – csak adatmegjelenítő réteg              [döntve 2026-06-21]
```

→ Részletes fázisok: [`megvalositasi-terv.md`](megvalositasi-terv.md)

---

## Következő lépések

- [x] **Helyszín felmérés** – beltéri, WiFi garantált
- [ ] **GSM 2. fázis firmware** – 4G router + ESPHome vs. TinyGSM egyedi → [`kommunikacio.md`](kommunikacio.md#esphome-és-gsm--fontos-korlát-2026-06-23)
- [ ] **Eszközcsalád pontosítása** – hőmérséklet/páratartalom, relé, mozgásérzékelő ismert; ventilátor + gépmoniror új termékként szóba jött
- [x] **Csapat technológiai ismerete** – Python/FastAPI stack kiválasztva
- [ ] **MVP scope meghatározása** – 1. fázis: adatgyűjtés + dashboard → [`megvalositasi-terv.md`](megvalositasi-terv.md)
- [ ] **GDPR / adatvédelem** – szerbiai vs EU adattárolás jogi vizsgálata szükséges
- [ ] **EMQX autentikáció** – eszköz azonosítási módszer kiválasztása
- [ ] **Szerver platform döntés** – ThingsBoard vs FastAPI stack véglegesítése → [`thingsboard-dontes.md`](thingsboard-dontes.md)
- [ ] **Firmware döntés** – ESPHome vs Tasmota véglegesítése → [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md)
- [ ] **Mobilalkalmazás / provisioning döntés** – választott irány: saját backend + szerelői felület (ESPHome Captive Portal Wi-Fi-hez); részletek: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md)
- [ ] **Dashboard** – Grafana + web UI az 1. fázisban (adatmegjelenítés)
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
- Panic button: jelenlét szenzor + AI szokásprofil – milyen riasztási küszöbök?
- BLE személy-érzékelés: MAC randomization, GDPR, Tasmota vs custom firmware?
