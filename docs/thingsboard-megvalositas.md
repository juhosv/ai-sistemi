# ThingsBoard + ESPHome – Megvalósítási terv (lépésről lépésre)

> **Státusz:** Tervezett implementáció – 2026-06-23  
> **Kapcsolódó:** [`thingsboard-dontes.md`](thingsboard-dontes.md), [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md), [`kommunikacio.md`](kommunikacio.md)

A rendszer **Linux szerveren**, **Docker Compose**-szal fut. Célok:

- Egyedi hardverek **kódmentes** helyszíni üzembe helyezése (Captive Portal)
- **Helyi logika** az eszközön (pl. hőmérséklet → PWM), offline is
- Eszköz **automatikus megjelenése** a szerveren MQTT csatlakozáskor
- **ThingsBoard CE:** multi-tenant hierarchia, Rule Engine adatdúsítás, ügyfél dashboard

---

## Áttekintés – öt fázis

| Fázis | Hol | Eredmény |
|-------|-----|----------|
| **1** | Linux szerver | ThingsBoard CE + PostgreSQL (Docker) |
| **2** | Fejlesztő PC | ESPHome flotta mintasablon (YAML → `.bin`) |
| **3** | Helyszín (szerelő) | Wi-Fi beállítás, első MQTT kapcsolat |
| **4** | TB admin | Customer → Asset → Device hierarchia + Rule Chain |
| **5** | TB admin + ügyfél | Dashboard widgetek, csúszkák, megosztás |

```
Műhely          Helyszín              Szerver (Docker)
──────          ────────              ────────────────
ESPHome flash   Captive Portal Wi-Fi  ThingsBoard CE
.bin            → MQTT connect        → Device megjelenik
                                      → Admin: hierarchia
                                      → Rule Engine: meteo + stat
                                      → Dashboard → ügyfél
```

---

## 1. fázis – Szerver környezet (Docker)

### Előfeltételek

- Linux szerver (VPS: Hetzner, DigitalOcean stb.) – min. ~4 GB RAM pilotra
- Docker + Docker Compose telepítve
- Nyitott portok: **8080** (web UI), **1883** (MQTT)

### Könyvtár

```bash
sudo mkdir -p /opt/thingsboard-fleet
cd /opt/thingsboard-fleet
```

### `docker-compose.yml`

```yaml
version: "3.8"

services:
  mytb:
    image: thingsboard/tb-postgres:latest
    container_name: thingsboard
    ports:
      - "8080:9090"   # Web UI (konténerben 9090 – ha nem működik, próbáld 8080:8080)
      - "1883:1883"   # MQTT – ESP eszközök
      - "7070:7070"   # Edge RPC (opcionális)
    environment:
      TB_QUEUE_TYPE: in-memory
    volumes:
      - mytb-data:/data
      - mytb-logs:/var/log/thingsboard
    restart: always

volumes:
  mytb-data:
  mytb-logs:
```

> **Megjegyzés:** A hivatalos image (`thingsboard/tb-postgres`) PostgreSQL-t is tartalmaz. A port mapping ellenőrizendő az első indítás után – lásd [ThingsBoard Docker install](https://thingsboard.io/docs/user-guide/install/docker/).

### Indítás

```bash
docker compose up -d
docker compose logs -f mytb   # első indulás: több perc
```

### Első belépés

| | |
|---|---|
| URL | `http://<szerver_ip>:8080` |
| Alap admin | `sysadmin@thingsboard.org` / `sysadmin` |

**Azonnal változtasd meg** a sysadmin jelszót éles környezetben.

### MQTT – fontos beállítások (pilot előtt)

| Téma | Teendő |
|------|--------|
| Eszköz hitelesítés | ThingsBoard MQTT: **username = device access token** (szabvány) |
| Automatikus regisztráció | Device Profile + **Provisioning** vagy manuális Device létrehozás – pilotban döntendő |
| TLS | Később: 8883 + tanúsítvány |

→ Részletes döntés: [`thingsboard-dontes.md`](thingsboard-dontes.md)

---

## 2. fázis – ESPHome flotta mintasablon

Egyszer megírt **„recept”** – minden egyedi hardverre ugyanaz a logika: Captive Portal, MQTT, helyi PWM szabályozás, ThingsBoard-ról állítható határértékek.

### Fájl: `fleet-device.yaml` (fejlesztői gépen / CI)

```yaml
esphome:
  name: fleet-device
  name_add_mac_suffix: true   # egyedi név MAC alapján: fleet-device-aabbcc
  friendly_name: "Flotta eszköz"
  project:
    name: "smartblue.vezerlo"
    version: "1.0.0"

esp32:
  board: esp32dev
  # ESP8266 esetén: esp8266: board: d1_mini

# --- Helyszíni Wi-Fi (szerelő) ---
wifi:
  ap:
    ssid: "OkosEszkoz_Telepites"
    password: !secret ap_password   # opcionális, de ajánlott

captive_portal:

# --- MQTT → ThingsBoard ---
# Pilot: cseréld a placeholdereket; élesben secrets / per-device token
mqtt:
  broker: !secret tb_broker_ip
  port: 1883
  username: !secret tb_device_token   # ThingsBoard device access token
  password: ""
  discovery: false
  # TB telemetry formátum – pilotban topic mapping ellenőrizendő
  # Részletek: lásd „MQTT integráció” szekció alább

logger:
  level: INFO

ota:
  password: !secret ota_password

# --- Hardver: hőmérséklet → kimenet ---
# DC ventilátor: ledc PWM (lásd alább)
# AC ventilátor (230 V triak): ac_dimmer – lásd projekt-ventilator.md

output:
  - platform: ledc
    pin: GPIO23
    id: pwm_kimenet

sensor:
  - platform: dht
    pin: GPIO22
    model: DHT22
    temperature:
      name: "Belso Homerseklet"
      id: belso_temp
      on_value:
        then:
          - output.set_level:
              id: pwm_kimenet
              level: !lambda |-
                float temp = x;
                float t_min = id(also_hatar).state;
                float t_max = id(felso_hatar).state;
                if (t_max <= t_min) return 0.0;

                float norm = (temp - t_min) / (t_max - t_min);
                if (norm <= 0.0) return 0.0;
                if (norm >= 1.0) return id(max_fordulat).state / 100.0;

                float min_pct = id(min_fordulat).state / 100.0;
                float max_pct = id(max_fordulat).state / 100.0;
                if (max_pct < min_pct) max_pct = min_pct;

                return min_pct + norm * (max_pct - min_pct);

# ThingsBoard Shared Attributes / RPC – restore_value: offline + áramszünet után is megmarad
number:
  - platform: template
    name: "also_hatar"
    id: also_hatar
    min_value: 10
    max_value: 40
    step: 1
    optimistic: true
    restore_value: true
    initial_value: "20"

  - platform: template
    name: "felso_hatar"
    id: felso_hatar
    min_value: 20
    max_value: 60
    step: 1
    optimistic: true
    restore_value: true
    initial_value: "30"

  - platform: template
    name: "min_fordulat"
    id: min_fordulat
    min_value: 0
    max_value: 100
    step: 1
    unit_of_measurement: "%"
    optimistic: true
    restore_value: true
    initial_value: "20"

  - platform: template
    name: "max_fordulat"
    id: max_fordulat
    min_value: 0
    max_value: 100
    step: 1
    unit_of_measurement: "%"
    optimistic: true
    restore_value: true
    initial_value: "100"
```

> **AC ventilátor (triak + nullátmenet):** cseréld a `ledc` blokkot `ac_dimmer`-re (`gate_pin`, `zero_cross_pin`, `method: leading pulse`). Részletesen: [`projekt-ventilator.md`](projekt-ventilator.md#esphome--komplex-helyi-logika-ac-triak).

### Fordítás és flash (műhely)

```bash
esphome compile fleet-device.yaml
esphome run fleet-device.yaml    # első alkalommal USB
# vagy web.esphome.io – .bin feltöltés
```

A kész `.bin` minden azonos pinout-ú eszközre égethető – **nincs eszközönként külön YAML** a helyszínen.

### MQTT integráció – pilot előtt ellenőrizendő ⚠

A ThingsBoard MQTT API elvárása:

| Elem | ThingsBoard szabvány |
|------|----------------------|
| Auth | `username` = **device access token** |
| Telemetria topic | `v1/devices/me/telemetry` |
| Payload | JSON: `{"Belso Homerseklet": 24.5}` |
| Attribútum (szerver → eszköz) | Shared attributes / RPC |

Az ESPHome alap MQTT komponense **saját topic struktúrát** használ (`<prefix>/sensor/.../state`). A pilot feladata:

- [ ] ESPHome → TB telemetry mapping (custom `mqtt` publish / `on_value` JSON, vagy köztes gateway)
- [ ] `also_hatar` / `felso_hatar` / `min_fordulat` / `max_fordulat` TB Shared Attribute → ESPHome `number` szinkron
- [ ] Eszköz provisioning: token előre beégetve *vs.* TB provisioning rule MAC alapján

→ Kapcsolódó: [`mqtt-protokoll.md`](mqtt-protokoll.md) – ESPHome/TB ág definiálandó

---

## 3. fázis – Szerelő helyszíni munkafolyamata

**Kód nélkül** – csak telefon:

| Lépés | Mi történik |
|-------|-------------|
| 1. Áram | Eszköz indul → nincs mentett Wi-Fi → **OkosEszkoz_Telepites** hotspot |
| 2. Wi-Fi | Szerelő telefonja csatlakozik → **Captive Portal** (vagy `192.168.4.1`) → ügyfél SSID + jelszó |
| 3. Csatlakozás | Eszköz internetre kapcsol → **MQTT** → ThingsBoard szerver |
| 4. Megjelenés | Admin látja az új eszközt (Devices) – MAC / név alapján |

A szerelő **nem** nyit YAML-t, **nem** flash-el, **nem** lép be a TB-be (opcionálisan később: szerelői app).

→ Részletek: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md#választott-flotta-architektúra-3-megoldás)

---

## 4. fázis – Hierarchia és adatdúsítás (ThingsBoard admin)

### 4.1 Ügyfelek és csoportosítás

| Lépés | Menü | Példa |
|-------|------|-------|
| 1 | **Customers** | Új ügyfél: *Kovács János* |
| 2 | **Assets** | Hierarchia: *Kovács János nyaralója* → *Hátsó szoba* |
| 3 | **Devices** | Új MQTT eszköz megjelenik → átnevezés: *Hátsó szoba érzékelője* |
| 4 | Hozzárendelés | Device → Asset (*Hátsó szoba*) → Customer (*Kovács János*) |

Az Asset-hez érdemes **Server attribute**-ként tárolni a **GPS koordinátákat** (meteo Rule-hoz).

### 4.2 Rule Chain – adatdúsítás (Rule Engine)

**Rule Chains** → Root rule chain szerkesztése (vagy eszköz-specifikus chain):

```
[Message: Post telemetry]
        │
        ▼
[REST API Call]  ──► Open-Meteo (koordináta az Asset attribútumból)
        │
        ▼
[Script / Transform]  ──► temp_kulonbseg = belso - kulso
        │
        ▼
[Save Timeseries]  ──► belso + kulso + temp_kulonbseg → PostgreSQL idősor
```

**Script példa (Transform):**

```javascript
metadata.temp_kulonbseg = msg.Belso_Homerseklet - msg.external_temp;
return { msg: msg, metadata: metadata };
```

> A mezőneveknek egyezniük kell az ESPHome / MQTT telemetry kulcsokkal – pilot után véglegesítendő.

→ Részletes Rule Engine leírás: [`thingsboard-dontes.md`](thingsboard-dontes.md#adatfeldolgozás--rule-engine-dúsítás-statisztika-külső-adatok)

---

## 5. fázis – Dashboard az ügyfélnek

**Dashboards** → új dashboard → widgetek:

| Widget | Adat / vezérlés |
|--------|-----------------|
| **Time series chart** | `Belso Homerseklet`, `external_temp`, opcionálisan `temp_kulonbseg` |
| **Analog gauge** | Aktuális belső hőmérséklet |
| **Slider (Control widget)** | `also_hatar`, `felso_hatar` – hőmérséklet határok |
| **Slider** | `min_fordulat` (default 20 %), `max_fordulat` (default 100 %) |

**Megosztás:** Dashboard → Share → Customer *Kovács János*

**Ügyfél élmény:** bejelentkezés → csak a saját dashboard → csúszka mozgatás → MQTT RPC → ESP azonnal új határértékkel szabályozza a PWM-et (Wi-Fi kapcsolat mellett).

→ PWM logika: [`thingsboard-dontes.md`](thingsboard-dontes.md#példa-hőmérséklet--pwm-szabályozás-felhasználói-csúszkákkal), [`projekt-ventilator.md`](projekt-ventilator.md)

---

## Biztonság és üzemeltetés (éles előtt)

| Téma | Teendő |
|------|--------|
| Admin jelszó | Sysadmin jelszó csere |
| MQTT | TLS (8883), eszközönkénti access token |
| Captive Portal AP | `ap_password` beállítása |
| OTA | `ota_password` minden eszközön |
| Backup | `mytb-data` volume mentése |
| Domain | Reverse proxy (nginx) + `.rs` domain + HTTPS |

---

## Pilot checklist

### Szerver
- [ ] Docker Compose felállt, TB UI elérhető
- [ ] MQTT port 1883 elérhető kívülről (tűzfal)
- [ ] Sysadmin jelszó megváltoztatva

### Firmware
- [ ] `fleet-device.yaml` lefordítva, egy teszt ESP32-re flash
- [ ] Captive Portal + helyszíni Wi-Fi teszt
- [ ] MQTT kapcsolat TB-hez, telemetria megjelenik
- [ ] `also_hatar` / `felso_hatar` / `min_fordulat` / `max_fordulat` írható TB-ből

### Üzleti folyamat
- [ ] Customer + Asset + Device hierarchia teszt
- [ ] Rule Chain: Open-Meteo + temp_kulonbseg
- [ ] Dashboard + customer share
- [ ] Szerelői folyamat végigjátszva (kód nélkül)

---

## Kapcsolat a projekt fázisokkal

| [`megvalositasi-terv.md`](megvalositasi-terv.md) | Ez a dokumentum |
|--------------------------------------------------|-----------------|
| 1. fázis: adatgyűjtés + dashboard | **1–5. fázis** lefedi a teljes pilotot TB-vel |
| 2. fázis: OTA flotta, szabályzás | FOTA (TB Firmware), további Rule Chains |
| Korábbi FastAPI stack | Felváltva / kiváltva ThingsBoard CE-vel |

---

## Források

- [ThingsBoard – Docker installation](https://thingsboard.io/docs/user-guide/install/docker/)
- [ThingsBoard – MQTT API](https://thingsboard.io/docs/reference/mqtt-api/)
- [ThingsBoard – Rule Engine](https://thingsboard.io/docs/user-guide/rule-engine-2-0/overview/)
- [ESPHome – Captive Portal](https://esphome.io/components/captive_portal.html)
- [ESPHome – MQTT](https://esphome.io/components/mqtt.html)
