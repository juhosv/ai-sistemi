# Szerver döntés – ThingsBoard

> **Státusz:** Döntés előkészítés – valószínűleg **ThingsBoard CE** (ön-hosztolt, ingyenes licenc) (2026-06-23)  
> **Kapcsolódó:** [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md), [`szerver-architektura.md`](szerver-architektura.md), [`dontes-elokeszito.md`](dontes-elokeszito.md)

A korábbi terv **EMQX + FastAPI + PostgreSQL + InfluxDB + saját dashboard** volt (2026-05-19). A flotta-menedzsment, multi-tenant felhasználókezelés, vizuális dashboard és távoli konfiguráció/FOTA igények alapján a **ThingsBoard** kerül előtérbe – ez egy beépített IoT platform, nem csak MQTT broker.

---

## Miért ThingsBoard?

| Követelmény | Saját FastAPI stack | ThingsBoard |
|-------------|---------------------|-------------|
| Eszközmenedzsment (flotta) | Saját fejlesztés | **Beépített** |
| Multi-tenant (ügyfél / szerelő / admin) | Saját auth + DB | **Customers, Tenants, Roles** |
| Dashboard felhasználónak | Grafana + custom UI | **Vizuális dashboard szerkesztő** |
| Távoli paraméter módosítás | MQTT + saját API | **Shared Attributes, RPC** |
| Firmware OTA (FOTA) | Saját fejlesztés | **Beépített OTA kezelő** |
| Eszköz provisioning | Saját admin UI | **Device profiles, asset hierarchy** |
| YAML szerkesztés ESPHome-hoz | ESPHome Dashboard / CLI | **Nincs** – külön toolchain |
| Adatdúsítés, külső API, statisztika | FastAPI scheduler + batch job | **Rule Engine** (vizuális) |
| Tendenciák, aggregációk | InfluxDB + derived job | **Analytics / Aggregate** beépített |

**Előzetes javaslat:** ThingsBoard a központi IoT platform; ESPHome a firmware; a kettő **MQTT-n** kapcsolódik – a komplex helyi logika (triak, PWM) a chipen marad, a szerver csak JSON telemetriát és attribútumokat lát. → [`mqtt-protokoll.md`](mqtt-protokoll.md#esphome--thingsboard-ce--mqtt-architektúra)

---

## ThingsBoard és ESPHome kapcsolata

A ThingsBoard és az ESPHome **két külön projekt**. A ThingsBoard felületén **nincs** gomb az ESPHome YAML közvetlen szerkesztésére, újrafordítására és feltöltésére.

| Mit csinál a ThingsBoard | Mit csinál az ESPHome |
|--------------------------|----------------------|
| Eszközök regisztrálása, hierarchia, dashboard | Firmware generálás YAML-ből |
| Telemetria fogadás, tárolás, megjelenítés | Szenzor olvasás, PWM, helyi logika |
| Attribútumok / RPC → eszköz paraméterek | MQTT-n fogadja és NVS-ben tárolja |
| FOTA – `.bin` terjesztés flottára | OTA letöltés és flash |
| Ügyfél dashboardok, jogosultságok | Offline működés szerver nélkül is |

**Követelmény az első flash-nél:** az ESPHome konfigurációt **dinamikus üzemmódra** kell állítani (MQTT, template `number`/`switch` entitások, `restore_value: true`), hogy a ThingsBoard utólag tudjon paraméterezni és FOTA-zni.

---

## Utólagos konfiguráció – három szint

### 1. Dinamikus paraméterek (kódolás nélkül, azonnal)

Olyan működési paraméterek, amelyekhez **nem kell újrafordítani** a firmware-t:

- mozgásérzékelő érzékenység
- LED villogási sebesség
- hőmérséklet-jelentés gyakorisága
- PWM alsó/felső hőmérséklet határérték

**ESPHome oldal:** fix számok helyett `template` `number` entitások, `restore_value: true` (NVS), MQTT-n írható/olvasható.

**ThingsBoard oldal:** Dashboard widget (Slider, Input) → **Shared Attribute** vagy **RPC** → MQTT üzenet az eszköznek → ESP azonnal alkalmazza, újraindítás nélkül.

```
User csúszkát mozgat → TB Shared Attribute / RPC → MQTT → ESPHome number entitás → NVS mentés → azonnali hatás
```

### 2. Teljes szoftverváltás (FOTA a ThingsBoard-ból)

Ha a hardver logikája strukturálisan változik (új szenzor, átírt YAML):

1. Fejlesztő gépen: ESPHome CLI → `firmware.bin`
2. ThingsBoard: **Advanced → Firmware** → feltöltés, verziószám (pl. `v2.0.0`)
3. Eszközcsoport kiválasztása (pl. „Összes Kovács János féle nyomógomb”)
4. Firmware hozzárendelése → TB értesíti az eszközöket → letöltés, ellenőrzés, flash, újraindítás

### 3. Központi sablon kezelés (profi flotta – hibrid)

YAML szintű tömeges módosításhoz:

```
GitHub (ESPHome Packages sablonok)
        │
        ▼
CI/CD (GitHub Actions / Python script + esphome compile)
        │
        ▼
ThingsBoard REST API → .bin feltöltés + FOTA parancs flottára
```

| Lépés | Hol | Mi történik |
|-------|-----|-------------|
| Sablonok | Zárt GitHub repo | `Packages` + `Substitutions` – eszköztípusonként |
| Fordítás | CI/CD szerver | `esphome compile` → `.bin` per típus/verzió |
| Terjesztés | ThingsBoard API | Automatikus firmware feltöltés + csoportos FOTA |

---

## Példa: hőmérséklet → PWM szabályozás felhasználói csúszkákkal

Gyakori minta: minél melegebb, annál nagyobb PWM; a user állítja az alsó és felső hőmérséklet határt a dashboardon. **Offline is működik** – az ESP a flash memóriában tárolt határértékek szerint szabályoz.

### ESPHome sablon (lényeg)

```yaml
output:
  - platform: esp8266_pwm   # ESP32-n: ledc
    pin: D2
    id: pwm_kimenet

sensor:
  - platform: dht
    pin: D1
    temperature:
      name: "Helyszíni Hőmérséklet"
      id: homerseklet_szenzor
      on_value:
        then:
          - output.set_level:
              id: pwm_kimenet
              level: !lambda |-
                float temp = x;
                float t_min = id(also_hatar).state;
                float t_max = id(felso_hatar).state;
                if (t_max <= t_min) return 0.0;
                float pwm = (temp - t_min) / (t_max - t_min);
                if (pwm < 0.0) pwm = 0.0;
                if (pwm > 1.0) pwm = 1.0;
                return pwm;

number:
  - platform: template
    name: "Alsó hőmérséklet határ"
    id: also_hatar
    min_value: 10
    max_value: 40
    step: 1
    optimistic: true
    restore_value: true

  - platform: template
    name: "Felső hőmérséklet határ"
    id: felso_hatar
    min_value: 20
    max_value: 60
    step: 1
    optimistic: true
    restore_value: true
```

### ThingsBoard összekötés

| ESPHome entitás | ThingsBoard típus | Dashboard widget |
|-----------------|-------------------|------------------|
| Helyszíni Hőmérséklet | Telemetry | Hőmérő / grafikon |
| Alsó / Felső határ | Shared Attribute | Slider / Input (Control Widgets) |

**User flow:**
1. Admin: **Customers** → „Kovács János” + belépési adatok
2. Eszköz hozzárendelése az ügyfélhez
3. Dashboard megosztása az ügyféllel
4. János csúszkát mozgat → MQTT → ESP NVS mentés → PWM azonnal újraszámolódik

→ Kapcsolódó projekt ötlet: [`projekt-ventilator.md`](projekt-ventilator.md) – teljes paraméterkészlet: `also_hatar`, `felso_hatar`, **`min_fordulat` (20%)**, **`max_fordulat` (100%)**

### Nyitott részletek (vizsgálandó)

- [ ] ESPHome MQTT topic mapping ThingsBoard MQTT integrációhoz
- [ ] Csúszka validáció: alsó határ ne legyen a felső fölött (TB rule vagy widget constraint)
- [ ] Manuális / automatikus mód kapcsoló (user fix 100% PWM)

---

## Multi-tenancy a ThingsBoard-ban

A korábbi „saját PostgreSQL + user/ház/szoba” modell nagy része **natívan** megoldható:

| SmartBlue fogalom | ThingsBoard fogalom |
|-------------------|---------------------|
| Super user / admin | **Tenant Admin** vagy **SysAdmin** |
| Ügyfél (Kovács János) | **Customer** |
| Ház / ingatlan | **Asset** (hierarchikus) |
| Szoba | **Asset** (alárendelt) |
| Eszköz | **Device** (MAC / access token) |
| Szerelő | **User** megfelelő role-lal |

**Előny:** az ügyfél csak a neki megosztott dashboardot látja – nem kell külön React app az alaphoz.

---

## Javasolt architektúra (ThingsBoard + ESPHome)

```
┌─────────────────────────────────────────────────────────────┐
│                    ThingsBoard Platform                      │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Dashboard│  │ Device Mgmt│  │ Rule Eng.│  │ FOTA     │ │
│  │ (User UI)│  │ Customers  │  │ Alarms   │  │ Firmware │ │
│  └──────────┘  └────────────┘  └──────────┘  └──────────┘ │
│         MQTT Broker (beépített vagy külső EMQX)             │
└───────────────────────────┬─────────────────────────────────┘
                            │ MQTT
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ESPHome #1          ESPHome #2          ESPHome #N
   (ventilátor)        (érzékelő)          (…)
```

### Fejlesztési toolchain (nem éles szerver)

| Eszköz | Szerep |
|--------|--------|
| ESPHome CLI / Docker | Sablon YAML → `.bin` generálás |
| `web.esphome.io` | Első kábeles flash műhelyben |
| GitHub + CI/CD | Sablon verziókezelés, automatikus build |
| ThingsBoard REST API | FOTA feltöltés automatizálás |

### Mit **nem** kell (vagy kevésbé) saját fejlesztésben

- Saját MQTT→DB worker (TB fogadja a telemetriát)
- Saját dashboard framework (TB widgetek)
- Saját FOTA infrastruktúra
- Saját multi-tenant auth az alap IoT réteghez

### Mit **még mindig** lehet külön kelleni

| Terület | Megjegyzés |
|---------|------------|
| LLM / Hermes chat | Adatmegjelenítő réteg – TB API-ból vagy mellé |
| Speciális üzleti logika | **Rule Engine** (dúsítás, meteo, statisztika) – lásd alább |
| Email / SMS | TB alarm rules + notification channels, vagy Infobip integráció |
| Provisioning flow finomhangolás | TB device profile + asset assign; szerelői UX tervezés |
| White-label domain | TB custom branding |

---

## Kapcsolat az eddigi SmartBlue döntésekkel

| Eddigi döntés (2026-05-19) | ThingsBoard irány |
|----------------------------|-------------------|
| EMQX MQTT broker | TB **beépített MQTT** vagy külső EMQX – **döntendő** |
| FastAPI + aiomqtt | **Felváltva / csökkentve** – core IoT a TB-ben |
| PostgreSQL | TB saját DB-t használ (PostgreSQL/Cassandra) – metaadatok TB-ben |
| InfluxDB | TB idősor tárolás – **InfluxDB valószínűleg nem kell** az 1. fázishoz |
| Grafana + web UI | **TB dashboard** helyettesíti |
| MAC-suffix topic név | Kompatibilis – TB device access token / MQTT client ID |
| Tasmota teszt (Bálint) | Megtartva – tanulságok érvényesek MQTT-re |
| 1. fázis: adatgyűjtés + dashboard | **TB-vel gyorsabban** elérhető |

---

## Üzembe helyezési folyamat ThingsBoard-bal

A [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md) seamless provisioning modellje ThingsBoard-bal:

| Lépés | Hol | Mi történik |
|-------|-----|-------------|
| 1. Gyártás | Műhely | ESPHome flash generikus YAML + MQTT (TB broker címe), Captive Portal |
| 2. Wi-Fi | Helyszín | Szerelő: Captive Portal |
| 3. Első kapcsolat | Automatikus | Eszköz MQTT-n csatlakozik → TB-ben megjelenik (ha nincs regisztrálva: „unassigned”) |
| 4. Hierarchia | TB admin / szerelő | Customer → Asset (ház) → Asset (szoba) → Device assign + elnevezés |
| 5. Dashboard | TB | Widgetek automatikusan az eszköz telemetriájából / attribútumaiból |

Firmware **újraírás nélkül** rendelhető hierarchiához – csak TB metaadat.

---

## Adatfeldolgozás – Rule Engine (dúsítás, statisztika, külső adatok)

A ThingsBoard **maximálisan támogatja** azt a munkafolyamatot, amikor az ESPHome-tól érkező nyers telemetria **adatbázisba mentés előtt vagy közben** dúsítandó számított értékekkel, tendenciákkal vagy internetről letöltött nyilvános adatokkal (pl. meteorológia). Mindez a **Rule Engine** (Szabálymotor) – vizuális, blokkalapú környezet, Node-RED-szerű – segítségével valósítható meg **kód nélkül vagy minimális scripttel**.

### Adatfolyam – áttekintés

```
ESPHome (nyers mérés) ──MQTT──► ThingsBoard
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Rule Engine      Rule Engine     Rule Engine
              (REST API)       (Script)        (Analytics)
              külső meteo      számítás        átlag/trend
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                         Egyesített telemetria rekord
                         (mért + számított + külső)
                                    │
                                    ▼
                              Adatbázis (idősor)
                                    │
                                    ▼
                              Dashboard widgetek
```

**Elv:** a filléres helyszíni hardver **csak mér és szabályoz** – nem hív internetes API-kat, nem tárol historikus adatot tendenciákhoz. A „nehéz” számítás, dúsítás és archiválás a **szerveren** történik.

---

### 1. Külső adatok behúzása (meteorológia)

Amikor az ESP beküldi a belső hőmérsékletet, a Rule Engine **ugyanabban a feldolgozási lépésben** lekérheti a házhoz tartozó külső időjárás-adatot.

| Lépés | Rule Engine blokk | Mi történik |
|-------|-------------------|-------------|
| 1 | **Message** trigger | Beérkezik az ESP telemetria (pl. `belső_hőmérséklet`) |
| 2 | **REST API Call** | HTTP kérés meteo szolgáltató felé (koordináta vagy város az Asset attribútumból) |
| 3 | **Script** / **Transform** | Válaszból kinyerés: külső hő, pára, szél, csapadék |
| 4 | **Save telemetry** / **Originator Attributes** | Külső mezők hozzáadása ugyanahhoz a rekordhoz |
| 5 | Mentés | Egyetlen idősor-rekord: mért + külső adatok |

**Lehetséges API-k** (Szerbia pilot – nyitott döntés):

| Szolgáltató | Megjegyzés |
|-------------|------------|
| [Open-Meteo](https://open-meteo.com/) | Ingyenes, API kulcs nélkül, EU lefedettség |
| OpenWeatherMap | API kulcs kell, széles körű |

A ház **földrajzi koordinátái** az Asset **Server-side attribute**-ként tárolhatók (szerelő állítja be provisioningkor) – a Rule ebből kérdez le.

→ Kapcsolódó: mezőgazdasági pilot ([`termek-otletek.md`](termek-otletek.md)), [`megvalositasi-terv.md`](megvalositasi-terv.md) ③ külső adatok

---

### 2. Számított statisztikák és tendenciák

#### Matematikai számítások (Script blokk)

JavaScript vagy TBEL (ThingsBoard Expression Language) kifejezéssel, **valós időben** az új mérés beérkezésekor:

| Számított mező | Példa képlet |
|----------------|--------------|
| Hőmérséklet-különbség | `belső_hő - külső_hő` |
| Harmatpont | standard meteorológiai képlet |
| Komfort index | egyedi üzleti logika |

#### Aggregációk és tendenciák

| Funkció | Leírás | Példa |
|---------|--------|-------|
| **Analytics / Aggregate** | Beépített: átlag, min, max időablakon | Elmúlt 1 óra / 24 óra / 7 nap átlag |
| **Historikus összehasonlítás** | Script: mostani vs. 1 órával ezelőtti | `tendencia: "emelkedő"` / `"csökkenő"` |
| **Delta** | Változás mértéke időben | `+2.3 °C / óra` |

Példa tendencia logika:
```
ha (mostani_érték - érték_1_órával_ezelőtt) > 0  →  tendencia = "emelkedő"
ha < 0                                           →  tendencia = "csökkenő"
egyébként                                         →  tendencia = "stabil"
```

A számított mezők **ugyanúgy telemetria kulcsokként** kerülnek mentésre, mint a chip által mért értékek.

---

### 3. Megjelenítés a Dashboardon

Mivel a Rule Engine az összes dúsított adatot **beleírja az eszköz idősor-rekordjába**, a dashboard szerkesztőben ezek **normál telemetria adatokként** jelennek meg – nincs külön „számított réteg” API.

| Widget típus | Mit mutat | Adatforrás |
|--------------|-----------|------------|
| **Time series chart** | Mért + külső + átlag egy diagramon | `belső_hő`, `külső_hő`, `átlag_24h` |
| **Analog gauge** | Aktuális érték | Mért telemetria |
| **Trend indicator** | Fel/le nyíl, szín | `tendencia` attribútum (zöld/piros) |
| **Entity table** | Összesítő táblázat | Aggregált mezők |
| **Time window** | Beépített időválasztó | Utólagos havi/heti statisztikák |

**User példa (Kovács János dashboard):**
- Egy grafikon: helyszíni hőmérséklet + külső (internetes) hőmérséklet + elmúlt 24 óra átlaga
- Trend widget: fűtési igény emelkedik/csökken (színkódolt)
- Idősor böngésző: elmúlt hónap heti átlagai

A ThingsBoard idősor-adatbázisa a **time-series** lekérdezéseket gyorsan szolgálja ki – a user a felületen visszamenőleg is böngészhet.

---

### Miért ideális ez a SmartBlue architektúrához?

| Réteg | Feladat | Hol fut |
|-------|---------|---------|
| **ESPHome / ESP** | Mérés, PWM, helyi szabályozás, offline működés | Eszközön |
| **ThingsBoard Rule Engine** | Meteo letöltés, statisztika, tendencia, riasztás | Szerveren |
| **ThingsBoard Dashboard** | User felület, grafikonok, csúszkák | Szerveren (böngésző) |

Ez **felváltja** a korábbi tervben szereplő:
- FastAPI **meteo scheduler** (HTTP fetch)
- külön **derived job** / batch aggregáció
- **InfluxDB** mint kötelező idősor réteg (TB saját tárolást használ)

A [`megvalositasi-terv.md`](megvalositasi-terv.md) ①–④ adattípusai ThingsBoard-bal **egy platformon belül** kezelhetők – a felhasználói napló (②) és későbbi ML (④) még vizsgálandó (TB nem tárol szöveges naplót natívan → PostgreSQL mellé vagy custom entity).

### Rule Engine – nyitott kérdések

- [ ] Open-Meteo vs. OpenWeatherMap – Szerbia pilot API választás
- [ ] Meteo lekérés gyakorisága – minden telemetria üzenetnél vs. óránkénti cache
- [ ] Asset koordináták provisioning – szerelői űrlap ThingsBoard-ban
- [ ] Community Edition Rule Engine limitációk – pilot során ellenőrizendő
- [ ] Mezőgazdasági pilot: talajnedvesség + meteo összekapcsolás dashboardon
- [ ] Későbbi ML: TB Rule Engine elegendő, vagy Python microservice mellé?

---

## Licencelés és költségek

A ThingsBoard **ingyenesen használható** a **Community Edition (CE)** választása esetén. Apache 2.0 licenc, 100% nyílt forráskód – **kereskedelmi / üzleti projekthez is ingyenes**.

**Előzetes javaslat SmartBlue-hoz:** **ThingsBoard CE, ön-hosztolt** (Docker / Docker Compose saját VPS-en).

### Három üzemeltetési modell

| Modell | Szoftver költség | Üzemeltetés | SmartBlue |
|--------|------------------|-------------|-----------|
| **Community Edition (CE)** – ön-hosztolt | **0 Ft** – nincs eszköz-/user-/üzenet limit | Saját VPS (Hetzner, DO, AWS…) | **✓ Javasolt** |
| **ThingsBoard Cloud** – SaaS | Free csomag kisebb teszthez; fizetős sávok ~49 USD/hótól | ThingsBoard intézi | Pilot teszt opció |
| **Professional Edition (PE)** – ön-hosztolt | Fizetős licenc (vállalati) | Saját szerver | Nem szükséges induláskor |

### Community Edition – mi ingyenes?

| Tétel | CE |
|-------|-----|
| Szoftver licenc | Ingyenes, korlátlan eszköz és user |
| Multi-tenant (Customers) | ✓ |
| Rule Engine | ✓ |
| Dashboard, widgetek, csúszkák | ✓ |
| MQTT transport (ESPHome-hoz) | ✓ |
| FOTA | ✓ |
| Kereskedelmi használat | ✓ |

**Ami mégis költség:** csak a **saját szerver** havidíja – kisebb flottához tipikusan **5–15 EUR/hó** (VPS).

**Telepítés:** Docker vagy Docker Compose – összhangban a korábbi [`szerver-architektura.md`](szerver-architektura.md) deployment tervvel.

### ThingsBoard Cloud (SaaS)

| Csomag | Jellemző |
|--------|----------|
| **Free** | Éles környezetben kisebb méretű teszt, kötöttség nélkül |
| **Fizetős** (Prototype, Pilot, Startup, Business) | Eszközszám és üzenetmennyiség alapján, ~49 USD/hótól |

Hasznos **pilot / POC** fázisban, ha nem akarunk szervertelepítéssel foglalkozni – hosszú távon a CE + saját VPS olcsóbb nagyobb flottánál.

### CE vs Professional Edition (PE) – SmartBlue szempontból

| Funkció | CE | PE | SmartBlue megjegyzés |
|---------|----|----|----------------------|
| White-label (logó, branding) | Saját domain lehetséges; logó eltávolítás **CSS/forrás módosítás** | Beépített UI-ból | `.rs` domain – CE + kis CSS testreszabás valószínűleg elég |
| LoRaWAN / Sigfox integráció | – | ✓ | **Nem kell** – ESPHome tiszta MQTT |
| MQTT | ✓ beépített broker | ✓ | **Elég a CE** |
| Grafikon adat export (Excel/CSV) | Nincs UI gomb | ✓ egy kattintás | CE-ben **REST API**-val kinyerhető |
| Rule Engine | ✓ | ✓ bővített | Pilot előtt ellenőrizendő: CE limitációk elég-e |

### Összegzés

```
SmartBlue stack (előzetes):
  ESPHome (firmware)  →  MQTT  →  ThingsBoard CE (0 Ft licenc)
                                        ↑
                              Hetzner VPS (~5–15 EUR/hó)
```

A CE tartalmazza az eddig dokumentált funkciókat: flotta-menedzsment, Rule Engine (meteo, statisztika), dashboard, FOTA, multi-tenant ügyfélkezelés. A PE és Cloud csak akkor releváns, ha később beépített white-label vagy menedzselt felhő kell előfizetéses modellben.

---

## Nyitott kérdések és következő lépések

### Döntendő

- [x] **ThingsBoard edition** – **Community Edition (CE), ön-hosztolt** – ingyenes licenc, kereskedelmi használat OK → [Licencelés](#licencelés-és-költségek)
- [ ] **MQTT:** beépített TB broker vs külső EMQX
- [ ] **Hivatalos stack döntés** – Viktor, Zsolti, Bálint egyeztetés (FastAPI stack sorsa)
- [ ] **ThingsBoard Rule Engine pilot** – meteo dúsítás + tendencia számítás + dashboard grafikon → [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)
- [ ] **ESPHome ↔ TB MQTT mapping** – topic konvenció dokumentálása

### Technikai teendők

- [ ] Generikus ESPHome flotta YAML ThingsBoard MQTT-hez (dinamikus `number` entitásokkal)
- [ ] Device Profile sablon ThingsBoard-ban eszköztípusonként
- [ ] Asset hierarchia sablon (Customer → Ház → Szoba)
- [ ] FOTA pipeline: GitHub → CI → TB REST API
- [ ] Szerelői provisioning UX a TB felületen (unassigned devices workflow)

### Vizsgálandó

- ThingsBoard white-label CE-ben – CSS/forrás testreszabás (`.rs` domain)
- TB rule engine vs külön szabálymotor a 2. fázisban
- Bálint meglévő teszt szerverének összehasonlítása TB-vel
- TB resource igény VPS-en (pilot méret)
- GDPR – TB self-hosted EU VPS

---

## Források

- [ThingsBoard – Installation (Docker)](https://thingsboard.io/docs/user-guide/install/docker/)
- [ThingsBoard – Pricing / Cloud](https://thingsboard.io/pricing/)
- [ThingsBoard – Calculated fields / analytics](https://thingsboard.io/docs/user-guide/calculated-fields/)
- [ThingsBoard – OTA updates](https://thingsboard.io/docs/user-guide/ota-updates/)
- [ThingsBoard – MQTT transport](https://thingsboard.io/docs/reference/mqtt-api/)
- [ESPHome – MQTT component](https://esphome.io/components/mqtt.html)
- Projekt: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md), [`szerver-architektura.md`](szerver-architektura.md), [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)
