# Megvalósítási terv

> **Döntés:** 2026-06-21 – kétfázisú megközelítés; **jelenleg az 1. fázisra koncentrálunk.**  
> **Szerver irány (2026-06-23):** ThingsBoard valószínű – adatdúsítás, meteo, statisztika a **Rule Engine**-ben → [`thingsboard-dontes.md`](thingsboard-dontes.md#adatfeldolgozás--rule-engine-dúsítás-statisztika-külső-adatok)  
> **Konkrét lépések:** [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md) – Docker, ESPHome sablon, szerelői folyamat, dashboard

---

## Összefoglaló

| Fázis | Cél | Státusz |
|-------|-----|---------|
| **1. fázis** | Adatgyűjtés, feldolgozás, dashboard megjelenítés | **Aktív – most ez a fókusz** |
| **2. fázis** | Szabályzás, konfig letöltés, eszközvezérlés, automatizálás | Tervezett – később |

---

## 1. fázis – Adatgyűjtés és megjelenítés

### Cél

Minél több releváns adat összegyűjtése és értelmezhető formában megjelenítése – **még szabályok, riasztások és eszközkonfiguráció nélkül** (vagy minimálisan).

```
Adatforrások                    Feldolgozás                    Megjelenítés
─────────────────              ─────────────                  ──────────────
① Szenzorok (MQTT)    ──┐
② Felhasználói napló  ──┼──► Normalizálás, tárolás  ──►  Dashboard
③ Külső API (meteo)   ──┤    (InfluxDB / PostgreSQL)       (Grafana / web UI)
④ Származtatott / ML  ──┘
```

### Mit **nem** tartalmaz az 1. fázis (2. fázisra halasztva)

- Eszközök távoli paraméterezése / konfig letöltés (OTA, `cmnd/` MQTT)
- Szabálymotor, automatikus riasztások, Node-RED flow-k
- AI-alapú eszközvezérlés
- LLM chat felület (csak később, adatmegjelenítő rétegként)

---

## Adattípusok (1. fázis)

### ① Szenzoroktól érkező adatok

| Forrás | Protokoll | Példa mezők | Tárolás |
|--------|-----------|-------------|---------|
| ESP32 + Tasmota | MQTT `tele/.../SENSOR` | hőmérséklet, pára, lux, jelenlét, talaj EC | InfluxDB |
| ESP32 események | MQTT `tele/.../SENSOR` (edge) | Switch, Button, PIR/LD2410 állapot | InfluxDB + eseménynapló |
| Eszköz meta | MQTT `tele/.../STATE`, LWT | WiFi RSSI, uptime, online/offline | PostgreSQL + InfluxDB |

→ Topic struktúra: [`mqtt-protokoll.md`](mqtt-protokoll.md)

### ② Felhasználók által feltöltött adatok (napló jellegű)

Szöveges vagy strukturált bejegyzések, amelyeket a felhasználó manuálisan rögzít – nem szenzorból jönnek.

| Példa | Leírás |
|-------|--------|
| Napi napló | „Ma rosszul éreztem magam", „Meglátogatta a látogató" |
| Mezőgazdasági jegyzet | „Ma trágyáztam", „Permetezés 8:00-kor" |
| Esemény jelölés | „Gép karbantartás", „Öntözés manuálisan" |

**Tárolás:** PostgreSQL (`user_journal` vagy hasonló tábla) – `user_id`, `timestamp`, `category`, `content` (szöveg / JSON).

**Cél:** később összekapcsolható a szenzor-idősorokkal és külső adatokkal (pl. „permetsz napokon magasabb páratartalom").

### ③ Internetről elérhető adatok

Külső API-kból periodikusan letöltött, helyhez/időhöz kötött adatok.

| Példa | Forrás | Gyakoriság |
|-------|--------|------------|
| Meteorológia | Nyilvános meteo API (csapadék, hő, pára, előrejelzés) | Óránként / eseményvezérelt |
| Naptár / ünnepnap | Opcionális – kontextus a szokásprofilhoz | Napi |

**ThingsBoard irány:** Rule Engine **REST API Call** blokk – meteo lekérés telemetria beérkezésekor vagy ütemezve; eredmény ugyanabba az idősor-rekordba mentve. Koordináták az Asset attribútumban.

**Korábbi terv (FastAPI stack):** InfluxDB – `source=external`, `provider=openmeteo` tag.

**Megjegyzés:** API választás és Szerbia lefedettség nyitott – lásd [`dontes-elokeszito.md`](dontes-elokeszito.md), [`thingsboard-dontes.md`](thingsboard-dontes.md).

### ④ Származtatott / statisztikai adatok (ML később)

A már rendelkezésre álló adatokból képzett új értékek – **1. fázisban egyszerű aggregáció**, később **ML (gépi tanulás)**.

| Szint | Példa | 1. fázis | Később (ML) |
|-------|-------|----------|-------------|
| Aggregáció | Órás / napi átlag hőmérséklet | ✓ Rule Engine Analytics | – |
| Trend | 7 napos mozgó átlag, emelkedő/csökkenő | ✓ Rule Engine Script | – |
| Összehasonlítás | Belső vs. külső hő különbség | ✓ Rule Engine Script | – |
| Anomália | – | – | Szokásprofil eltérés |
| Előrejelzés | – | – | Öntözési javaslat, riasztás |

**ThingsBoard irány:** számított mezők telemetriaként mentve → dashboard widgetek közvetlenül használják.

**Korábbi terv:** külön InfluxDB measurement (`derived`) vagy batch job; ML Python-ban (FastAPI).

---

## Adatfeldolgozási pipeline (1. fázis)

```
                    ┌─────────────────────────────────────────┐
                    │              EMQX (MQTT)                  │
                    └──────────────────┬──────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
  ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
  │ MQTT Worker  │            │  Scheduler   │            │  REST API    │
  │  (aiomqtt)   │            │ (meteo fetch)│            │ (napló CRUD) │
  └──────┬───────┘            └──────┬───────┘            └──────┬───────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  FastAPI – ingest   │
                          │  normalizálás       │
                          └──────────┬──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
             ┌──────────┐    ┌──────────┐    ┌──────────────┐
             │ InfluxDB │    │PostgreSQL│    │ Derived job  │
             │ idősor   │    │ meta +   │    │ (aggregáció) │
             │          │    │ napló    │    └──────┬───────┘
             └────┬─────┘    └────┬─────┘           │
                  │               │                 │
                  └───────────────┼─────────────────┘
                                  ▼
                          ┌──────────────┐
                          │  Dashboard   │
                          │ Grafana / UI │
                          └──────────────┘
```

---

## Dashboard (1. fázis)

**Cél:** az összegyűjtött adatok vizualizálása – grafikonok, táblázatok, idővonal.

| Megoldás | 1. fázis szerepe |
|----------|------------------|
| **Grafana** + InfluxDB | Gyors indulás, szenzor grafikonok, fejlesztői eszköz |
| **Egyedi web UI** (Bálint) | Felhasználói napló, összetett nézetek, multi-user |
| **LLM chat** (később) | **Csak adatmegjelenítő réteg** – lásd alább |

### Nyitott dashboard döntések

- [ ] Grafana elég az 1. fázisra, vagy azonnal egyedi UI is kell?
- [ ] Felhasználói napló bevitel hol történik? (web form, mobil?)
- [ ] Multi-user dashboard: user_id szerinti szűrés

---

## LLM chat – szerep a rendszerben (később, 2. fázis után)

> **Elv (2026-06-21):** A tervezett LLM-es chat felület **csak az adatok megjelenítését** szabad, hogy helyettesítse – **adatmegjelenítő rétegként** kell rá tekinteni.

| Mit csinálhat | Mit **nem** helyettesíthet |
|---------------|----------------------------|
| Természetes nyelvű lekérdezés („milyen volt a talajnedvesség tegnap?") | Eszközkonfiguráció letöltés / MQTT `cmnd/` |
| Összefoglaló, trend magyarázat | Szabálymotor, automatikus riasztás küldés |
| Grafikon / táblázat helyett szöveges válasz | Node-RED / hardver vezérlés |
| Ugyanazokat az adatokat mutatja, mint a dashboard | Új adatforrás önmagában (forrás továbbra is szenzor/API/napló) |

```
┌─────────────────────────────────────────────────────────┐
│  Adatmegjelenítő réteg (választható)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Dashboard   │  │   Grafana    │  │  LLM chat    │  │
│  │  (web UI)    │  │              │  │  (Hermes)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
              ┌─────────────────────────┐
              │  Közös adatréteg       │
              │  InfluxDB + PostgreSQL │
              └─────────────────────────┘
```

→ AI agent részletek: [`termek-otletek.md`](termek-otletek.md) – AI agent fejezet

---

## 2. fázis – Előzetes terv (nem aktív)

A 2. fázis **a 1. fázis adatbázisára épül** – addig gyűjtünk és tanulunk az adatokból.

| Terület | Tartalom |
|---------|----------|
| Szabályzás | Küszöbök, riasztási szabályok, Node-RED |
| Konfig letöltés | OTA / MQTT `cmnd/` – eszközparaméterek távoli állítása |
| Értesítések | Email, SMS, push – szabály alapú |
| AI vezérlés | Paraméterezés természetes nyelven (Node-RED integráció) |
| LLM UI | Chat mint adatmegjelenítő + később okosabb elemzés |

---

## 1. fázis – konkrét feladatok

- [ ] EMQX + InfluxDB + PostgreSQL + FastAPI ingest működő stack (Bálint)
- [ ] Szenzor MQTT → InfluxDB pipeline (legalább 1 eszköztípus)
- [ ] Otthoni / pilot eszközök üzembe helyezése, adatgyűjtés indul (Viktor, Zsolti)
- [ ] Felhasználói napló API + egyszerű beviteli felület (tervezés)
- [ ] Meteorológiai API integráció – első külső adatforrás
- [ ] Grafana dashboard – alap szenzor grafikonok
- [ ] Egyszerű aggregáció (órás/napi átlag) – derived adatok
- [ ] Multi-user adatelválasztás (`user_id` szűrés) – alapok

---

## Kapcsolódó dokumentumok

| Fájl | Tartalom |
|------|----------|
| [`szerver-architektura.md`](szerver-architektura.md) | Technológiai stack, komponensek |
| [`mqtt-protokoll.md`](mqtt-protokoll.md) | MQTT topic struktúra |
| [`dontes-elokeszito.md`](dontes-elokeszito.md) | Nyitott döntések |
| [`termek-otletek.md`](termek-otletek.md) | Termék ötletek, AI agent |
| [`PROJECT.md`](PROJECT.md) | Projekt kontextus |
