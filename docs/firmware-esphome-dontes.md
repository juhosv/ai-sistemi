# Firmware döntés – ESPHome vs Tasmota

> **Státusz:** Döntés előkészítés – valószínűleg **ESPHome** irány (2026-06-23)  
> **Kapcsolódó:** [`dontes-elokeszito.md`](dontes-elokeszito.md), [`szerver-architektura.md`](szerver-architektura.md), [`mqtt-protokoll.md`](mqtt-protokoll.md)

A pilot fázisban eddig **Tasmota** volt a választott firmware (sikeres end-to-end MQTT teszt 2026-05-27). A flotta-skálázás, központi konfiguráció-kezelés és multi-tenant üzembe helyezési igények alapján az **ESPHome** kerül előtérbe.

---

## Döntési kontextus

| Követelmény | Tasmota | ESPHome |
|-------------|---------|---------|
| Központi szerverrel kommunikáció | MQTT ✓ | MQTT ✓ (vagy Native API) |
| Távoli, központi konfiguráció-módosítás | Nehézkes (eszközönkénti WebUI) | **Központi YAML + OTA** |
| Többszintű csoportosítás (user → ház → szoba) | MQTT parancsok / TasmoAdmin | **Packages hierarchia** |
| Egyedi logika az eszközön | Rules / Berry | **automations, lambdas, C++** |
| Szerelő nem nyúl kódhoz | AP mód Wi-Fi beállítás ✓ | **Captive Portal** ✓ |
| Eszköz hierarchia és elnevezés szerveren | Adatbázisban (MAC alapú) | **Adatbázisban (MAC alapú)** – firmware újraírás nélkül |
| Saját egyedi hardver (D1 mini, pinout) | Generic Template | **Natív YAML pin definíció** |
| Eszköztípus sablon (pl. `nyomógomb_2_leddel`) | Template repo | **Packages + Substitutions** |
| GSM adat (MQTT mobilneten) | Korlátozott | **✗ gyári – lásd GSM szekció** |
| LoRa hatótáv (Wi-Fi helyett) | – | **✓ Packet Transport + gateway** |
| Arduino projekt kiváltása | C++ mindenhez | **~90–95%** – lásd [ESPHome vs Arduino](#esphome-vs-arduino--lefedettség-és-korlátok) |

**Előzetes javaslat:** ESPHome a végleges flotta-architektúrához; a meglévő Tasmota teszt és dokumentáció továbbra is értékes referencia.

---

## ESPHome – rövid bemutató

Az ESPHome nyílt forráskódú rendszer **egyedi firmware** generálására ESP8266/ESP32 chipekre. C/C++ helyett **YAML konfiguráció**; a rendszer ebből automatikusan legenerálja, lefordítja és feltölti a szoftvert.

### Fő jellemzők

| Jellemző | Leírás |
|----------|--------|
| Kódmentes fejlesztés | Hardver felépítése YAML-ben (lábkiosztás, szenzorok) |
| Home Assistant integráció | Native API – automatikus felismerés és entitás-létrehozás |
| Helyi vezérlés | Internet/felhő nélkül, adat a helyi hálózaton marad |
| Hardvertámogatás | Több száz natív szenzor, kijelző, relé, LED |
| OTA | Első kábeles flash után Wi-Fi-n frissíthető |

### SONOFF és gyári eszközök

Sok SONOFF (BASIC, S26, POW, TX) belsejében ESP8266/ESP32 van – átprogramozható ESPHome-ra (flashing). A gyári eWeLink felhő kiváltható lokális vezérléssel.

> **Fontos:** A SONOFF SNZB-06P jelenlét-érzékelőben **Zigbee** chip van, nem ESP – közvetlenül nem ESPHome-olható. Alternatíva: saját ESPHome radaros szenzor (pl. LD2410).

---

## ESPHome vs Arduino – lefedettség és korlátok

> **Kérdés:** Minden Arduino projekt megvalósítható ESP8266/ESP32 + ESPHome-mal, miközben szabadon megadható, mit küld a szervernek és mit állítunk távolról?

**Rövid válasz:** nagyjából **90–95% igaz** – a legtöbb okosotthon / IoT / épületautomatizálási projektre teljesen érvényes. A „minden” szó mérnökileg nem pontos; vannak speciális kivételek.

### SmartBlue / ThingsBoard szempontból – 100% igaz

| Követelmény | ESPHome megoldás |
|-------------|------------------|
| Távoli paraméterek | `number`, `select`, `switch`, `text` → ThingsBoard Shared Attributes / RPC |
| Adatküldés szerverre | `sensor`, `binary_sensor`, `text_sensor` → MQTT telemetria |
| Komplex helyi logika | `on_value`, `automation`, `then`, `!lambda` (pl. triak, ventilátor) |
| Egyedi pinout | YAML GPIO / busz definíció |
| Offline működés | `restore_value: true`, helyi automatizmusok |

### Hardvertámogatás (natív komponensek)

| Kategória | Példák |
|-----------|--------|
| Szenzorok | 500+ típus – hő, pára, lux, jelenlét, mmWave, talaj, áram |
| Kijelzők | OLED, TFT, E-paper, LCD |
| Aktuátorok | Relé, PWM, **`ac_dimmer`** (triak), LED, léptetőmotor |
| Buszok | I2C, SPI, 1-Wire (Dallas), UART |

### Hol NEM igaz az „minden Arduino projekt” állítás

| Eset | Miért nem elég a tiszta ESPHome | Alternatíva |
|------|----------------------------------|-------------|
| **Nagyon magas mintavételezés** | 40 kHz+ FFT, oszcilloszkóp – ms időzítésre optimalizált | Egyedi C++ / `custom_component` |
| **Extrém deep sleep (évek gombelemmel)** | Wi-Fi + MQTT kézfogás másodpercek – gyors lemerülés | Egyedi C++, ESP-NOW, LoRa, nem ESPHome stack |
| **Ritka ipari protokoll** | Nincs gyári komponens (pl. egyedi CAN, klíma busz) | Arduino library + `custom_component` |
| **GSM adatforgalom** | Nincs GPRS/4G IP gateway | 4G router + ESPHome, vagy TinyGSM C++ → [`kommunikacio.md`](kommunikacio.md) |

### Kiskapu: `custom_component`

Ha a gyári ESPHome nem tud valamit, **saját C++ kód** beágyazható – az ESPHome továbbra is kezeli:

- Wi-Fi, Captive Portal, OTA
- MQTT → ThingsBoard
- Flotta sablonok, Packages

A bonyolult algoritmus C++-ban marad; a kommunikáció és üzembe helyezés ESPHome-on.

### SmartBlue projektre – összegzés

| Feladat | ESPHome elegendő? |
|---------|-------------------|
| Hőmérséklet / pára mérés | ✓ |
| Ventilátor DC PWM vagy AC triak | ✓ |
| Távoli határértékek, min/max fordulat | ✓ |
| ThingsBoard dashboard + csúszkák | ✓ |
| Flotta provisioning (Captive Portal) | ✓ |
| Mezőgazdasági pilot (ritka küldés) | ✓ (hálózati táp) |
| Éves gombelem, óránként 1 üzenet | ⚠️ inkább egyedi firmware |

**Következtetés:** A SmartBlue eszközcsalád területén (fűtés/hűtés, ventilátor, szenzorok, ThingsBoard integráció) az ESPHome + ESP32 **teljes mértékben kiváltja** az Arduino IDE-s fejlesztést – és gyorsabb flotta-menedzsmentet ad, mint nulláról írt C++.

---

## ESPHome vs Tasmota – részletes összehasonlítás

### Alapfilozófia

| | ESPHome | Tasmota |
|---|---------|---------|
| Modell | **Szoftvergenerátor** – eszközönként egyedi, optimalizált bin | **Kész univerzális firmware** – feltöltés után WebUI konfig |
| Konfiguráció | YAML (PC-n / központi szerveren), feltöltés **előtt** | Webes felület, feltöltés **után** |
| Módosítás | Újrafordítás + OTA minden változáskor | Azonnali módosítás WebUI-n |

### 1. Tudás és rugalmasság

**ESPHome:** Rendkívül rugalmas – egyedi logika, edge computing, e-paper kijelzők, BLE beacon követés, LED animációk, mmWave radarok (gyakran előbb stabil támogatás). **Komplex hardver:** `ac_dimmer` (nullátmenet + triak), lambdák, PID – C interrupt kód nélkül → [`projekt-ventilator.md`](projekt-ventilator.md).

**Tasmota:** Kész funkciókészlet relékhez, dimmerekhez, alap szenzorokhoz. Bővítés Rules-szal vagy Berry szkripttel – bonyolultabb nagy flottánál.

### 2. Kommunikáció és integráció

| | ESPHome | Tasmota |
|---|---------|---------|
| Elsődleges protokoll | **Native API** (HA-hoz optimalizált, titkosított) | **MQTT** (univerzális ipari szabvány) |
| MQTT | Támogatott, de API az ajánlott HA mellett | Alapkő – HA, Domoticz, OpenHAB, Node-RED, Homey |
| WebUI | Nincs klasszikus eszköz-WebUI | Beépített HTTP vezérlőfelület |

**SmartBlue kontextus:** A célarchitektúra **ESPHome + ThingsBoard (MQTT)** – lásd [`thingsboard-dontes.md`](thingsboard-dontes.md). ESPHome MQTT módban használható Home Assistant nélkül is.

### 3. Támogatás és hardver

| | ESPHome | Tasmota |
|---|---------|---------|
| Dokumentáció | Kiváló, példakódok; Nabu Casa / HA csapat | Hatalmas Template Repository gyári eszközökhöz |
| Új szenzorok | Gyakran előbb (pl. mmWave) | Nagy gyári eszköz-lefedettség (Sonoff, Shelly…) |
| DIY hardver | **Erősség** – pinout teljes szabadság | Generic Template, kevésbé elegáns |

### 4. Elterjedtség

- **Tasmota:** Régebbi, hatalmas közösség; népszerű nem-HA rendszerekben.
- **ESPHome:** Robbanásszerű növekedés HA felvásárlás óta; HA környezetben iparági szabvány.

### Összegző táblázat

| Szempont | ESPHome | Tasmota |
|----------|---------|---------|
| Fő fókusz | Egyedi projektek, kijelzők, BLE | Okoskonnektorok, relék, fogyasztásmérők |
| Legjobb környezet | HA **vagy** saját MQTT backend | Bármi MQTT-alapú, nem csak HA |
| Kijelzők | Kiváló | Alapszintű (szöveg) |
| Flotta menedzsment | Központi Dashboard / API | Eszközönkénti IP + TasmoAdmin |

---

## Telepítés – lokális és OTA

Mindkét firmware támogatja a **kábeles első flash** és **OTA** frissítést; a folyamat logikája eltér.

| Szempont | Tasmota | ESPHome |
|----------|---------|---------|
| Mit töltesz fel? | Kész `.bin` az internetről | **Egyedi `.bin`** – a konfigurációdból generálva |
| Első telepítés | USB / Web Installer | USB + `web.esphome.io` vagy ESPHome CLI |
| Későbbi módosítás | WebUI vagy OTA fix bin | YAML módosítás → fordítás → OTA |
| Tasmota ↔ ESPHome | OTA-val átváltható mindkét irányban | |

**ESPHome első flash lépései:**
1. YAML konfiguráció megírása (központi felületen vagy CLI)
2. ESP USB-n csatlakoztatása
3. `web.esphome.io` (Chrome/Edge) – generálás és feltöltés egy kattintással
4. Később: központi szerverről **Install → Wireless / OTA**

OTA alapértelmezetten jelszóval védett.

---

## GSM kommunikáció – ESPHome korlátok

Az ESPHome **csak részben** támogatja a GSM-et. A flotta-architektúra (ESPHome → MQTT → ThingsBoard CE) **mobilneten keresztüli adatküldésre** gyári ESPHome megoldással **nem alkalmas** – csak Wi-Fi/Ethernet elsődleges kapcsolattal.

→ Részletes kommunikációs összehasonlítás: [`kommunikacio.md`](kommunikacio.md#esphome-és-gsm--fontos-korlát-2026-06-23)

### Mit tud az ESPHome natívan?

| Képesség | GPRS/4G adat (MQTT) | SMS / hívás |
|----------|---------------------|-------------|
| SIM800L komponens | ✗ | ✓ küldés, fogadás, Caller ID, USSD |
| MQTT → ThingsBoard | ✗ mobilneten | – |
| IP gateway (APN) | ✗ nincs gyári komponens | – |

**Következmény:** az ESPHome-on belüli MQTT kliens **nem csatlakozhat** a ThingsBoard-hoz közvetlenül GSM modulon keresztül.

### GSM adatkapcsolat – három alternatíva

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. TinyGSM (Arduino/C++)     ESP ──4G──► ThingsBoard (MQTT)    │
│    Nem ESPHome – egyedi firmware, ugyanaz a TB üzenetformátum   │
├─────────────────────────────────────────────────────────────────┤
│ 2. 4G Wi-Fi router (★)       ESP ─WiFi─► Router ─4G─► Internet  │
│    ESPHome változatlan – Captive Portal, OTA, sablon flotta     │
├─────────────────────────────────────────────────────────────────┤
│ 3. custom_component          ESPHome + egyedi C++ GSM kód       │
│    Haladó – elveszik a YAML egyszerűség                        │
└─────────────────────────────────────────────────────────────────┘
```

| Megoldás | ESPHome? | Mikor |
|----------|----------|-------|
| **4G router + Wi-Fi** | **Igen** | Mezőgazdaság, tanya – **javasolt**, ha marad az ESPHome toolchain |
| **TinyGSM (C++)** | Nem | LilyGO T-Call stb.; natív LTE; nincs Wi-Fi a helyszínen |
| **custom_component** | Részben | Csak ha mindenképp ESPHome + közvetlen GSM kell |
| **SMS only (SIM800L)** | Igen | Riasztás, nem adatcsatorna |

**Hardver példák TinyGSM-hez:** LilyGO T-Call ESP32; modulok: SIM7600, A7670 (4G/LTE – 2G kivezetés miatt SIM800L adatra nem ajánlott).

### SmartBlue döntési vonal

| Fázis | Kommunikáció | Firmware |
|-------|--------------|----------|
| Pilot (beltéri) | Wi-Fi | ESPHome |
| 2. fázis (terepi, 1NCE SIM) | GSM adat | **4G router + ESPHome** *vagy* TinyGSM egyedi FW |
| Kiegészítő | SMS riasztás | ESPHome SIM800L (opcionális) |

A ThingsBoard oldalon **mindegy**, melyik úton érkezik az MQTT – a szerver ugyanúgy fogadja az adatot.

---

## LoRa – hatótáv növelés (ESPHome + ThingsBoard)

**Igen, használható** hatótáv növelésre – de **nem Wi-Fi repeater**. A LoRa **külön 868 MHz-es rádiócsatorna**: Wi-Fi 20–50 m falak között, LoRa **1–5 km** szabad területen, jobban átmegy vastag falakon.

→ Részletes kommunikációs összehasonlítás: [`kommunikacio.md`](kommunikacio.md#4-lora-kommunikáció)

### Gateway–Node felépítés

A LoRa modul **nem tud MQTT-re csatlakozni** – kell egy **átjáró** Wi-Fi közelében:

| Eszköz | Szerep | ESPHome |
|--------|--------|---------|
| **Node** | Távoli szenzor (mező, pince, 200 m-re) | SX126x/127x + szenzorok; ritkán küld |
| **Gateway** | Főépület – LoRa fogad + **MQTT → ThingsBoard** | Wi-Fi + LoRa + MQTT ugyanazon boardon (pl. Heltec) |

### ESPHome natív támogatás

| Komponens | Funkció |
|-----------|---------|
| `sx126x` / `sx127x` | LoRa chip illesztés |
| **Packet Transport** | Node ↔ Gateway LoRa kommunikáció **YAML-ből**, C++ nélkül |
| MQTT (gateway-en) | Átjáró továbbítja a TB-re – ugyanaz a platform, mint Wi-Fi flottánál |

### Kompromisszumok

| Korlát | Hatás |
|--------|-------|
| Sávszélesség | Csak kis csomagok – **nincs FOTA** LoRa-n keresztül |
| Duty cycle (EU) | ~1% adásidő – küldés **1–5 percenként**, nem másodpercenként |
| Parancsok / csúszkák | ThingsBoard Shared Attribute **késleltetett** – nem azonnali PWM állítás |
| OTA node frissítés | Wi-Fi közelben vagy gateway mellett kábelesen |

### Ajánlott hardver

| Board | Használat |
|-------|-----------|
| **Heltec WiFi LoRa 32 (V3)** | Gateway (Wi-Fi + LoRa egy lapon) |
| **LilyGO T-Beam / T-Echo** | Távoli node (akkumulátoros) |
| **TTGO LoRa32** | Olcsó node |

### SmartBlue döntési vonal

| Helyszín | Megoldás |
|----------|----------|
| Beltéri pilot | Wi-Fi – LoRa nem kell |
| Wi-Fi a főépületben, szenzor **200+ m** | **LoRa node + 1 gateway** (ESPHome Packet Transport) |
| Nincs Wi-Fi, nincs GSM | LoRa node + gateway **4G backhaul**-lal *vagy* LoRaWAN |

**Összegzés:** LoRa + ESPHome + ThingsBoard **stabil, olcsó** megoldás nagy telephelyre – de **nem** helyettesíti a Wi-Fi azonnali vezérlését és OTA-ját.

---

## Home Assistant szerepe és korlátai

A HA **nem kötelező** a SmartBlue célarchitektúrához. Ha mégis használnánk:

### Mit tud a HA?

| Funkció | Admin | Sima User |
|---------|-------|-----------|
| ESPHome konfig szerkesztés | ✓ Beépített YAML editor + OTA | ✗ Menü elrejthető |
| Eszközök / Areas / Tags | Teljes hierarchia | Csak engedélyezett dashboard |
| Automatizálás | ✓ | Korlátozott |

### Multi-tenancy korlát

A HA filozófiája: **„egy szerver = egy háztartás”**. Több user / több ház egy HA instance-ben:

- Sima userek alapból **minden entitást látnak** (kereső, napló) – csak dashboard szűréssel rejthető el.
- Profi SaaS / vállalati flotta esetén a HA **nem ideális végfelhasználói felület**.

### Architektúra opciók (HA kontextusban)

| Verzió | Leírás | SmartBlue illeszkedés |
|--------|--------|----------------------|
| **A – Központi MQTT + saját backend** | ESPHome → EMQX → FastAPI + PostgreSQL + saját UI | **✓ Választott irány** |
| **B – Elosztott HA** | Házanként külön HA + központi menedzsment | Túl komplex flottához |

---

## Beüzemelés helyszínen

### Captive Portal (Tasmota AP mód megfelelője)

Ha a YAML-ben nincs előre megadott Wi-Fi:

```yaml
wifi:
  # nincs előre SSID/jelszó

captive_portal:
```

**Folyamat (szerelő):**
1. Eszköz áram alá → saját hotspot (eszköz nevével)
2. Telefon csatlakozik → automatikus portál vagy `192.168.4.1`
3. Elérhető hálózatok listája → SSID + jelszó → mentés
4. Eszköz csatlakozik, adatok megmaradnak áramszünet után is

### Flotta beüzemelési stratégiák

| Módszer | Mikor | Hogyan |
|---------|-------|--------|
| **Captive Portal** | Ügyfél saját Wi-Fi | Helyszíni telefonos beállítás |
| **Pre-staging** | Műhelyben teszt | Több Wi-Fi `priority`-val – részletek: [`kommunikacio.md`](kommunikacio.md#esphome--több-wi-fi-hálózat-elsődleges--másodlagos) |
| **Egységes fleet Wi-Fi** | Saját infrastruktúra (panzió, bérlemény) | Minden házban azonos rejtett SSID (pl. `smart-fleet`) – plug-and-play |

**Pre-staging YAML példa:**

```yaml
wifi:
  networks:
    - ssid: "Irodai_Telepito_WiFi"
      password: !secret office_wifi
      priority: 100
    - ssid: "Helyszini_Ugyfel_WiFi"
      password: !secret site_wifi
      priority: 50

captive_portal:
```

Alternatíva Captive Portal helyett: **Improv Wi-Fi** (Bluetooth-on keresztül, mobilapp).

---

## Egyedi hardver (DIY)

Az ESPHome **kifejezetten DIY-ra** optimalizált. Példa D1 mini + relé + gomb + LED:

```yaml
esphome:
  name: "egyedi-vezerlo-01"
  friendly_name: "Nappali Egyedi Vezérlő"

esp8266:
  board: d1_mini

binary_sensor:
  - platform: gpio
    pin: D1
    name: "Fali Kapcsoló"

switch:
  - platform: gpio
    pin: D2
    name: "Fő Világítás"

status_led:
  pin:
    number: D4
    inverted: true
```

**Előnyök Tasmotával szemben:** pullup/invert/delayed_on egy lábon, komplex gomblogika (hosszú/rövid nyomás) a chipen.

---

## Eszköztípus sablonok – Packages és Substitutions

Cél: egyszer megírt „recept” (`nyomógomb_2_leddel`), új eszköznél csak név és Wi-Fi.

### 1. Sablon fájl (`sablonok/nyomogomb_2_leddel.yaml`)

```yaml
substitutions:
  eszköz_neve: "alap-eszköz"
  baratsagos_nev: "Alap Eszköz"

esphome:
  name: ${eszköz_neve}
  friendly_name: ${baratsagos_nev}

esp8266:
  board: d1_mini

binary_sensor:
  - platform: gpio
    pin: D1
    name: "Nyomógomb"
# ... LED outputok, light komponensek ...
```

### 2. Új eszköz példa (`haloszoba-gomb.yaml`)

```yaml
packages:
  típus_sablon: !include sablonok/nyomogomb_2_leddel.yaml

substitutions:
  eszköz_neve: "haloszoba-gomb"
  baratsagos_nev: "Hálószobai Nyomógomb"

wifi:
  ssid: "Otthoni_WiFi"
  password: "titkosjelszavad"

captive_portal:
```

Sablon módosítása → OTA-val az összes azonos típusú eszköz frissül. Sablonok húzhatók **GitHub repóból** is.

---

## Üzembe helyezési megközelítések

| # | Megoldás | Leírás | SmartBlue |
|---|----------|--------|-----------|
| 1 | Web flash + HA auto-discovery | `web.esphome.io` + előre generált bin; HA felismeri fájl nélkül | Egyszerű, kevés flotta |
| 2 | HA + Node-RED űrlap | Dashboard űrlap → háttérben YAML generálás + compile | Közepes flotta |
| 3 | **ThingsBoard + ESPHome** | TB device/asset management, dashboard, FOTA; ESPHome generikus firmware | **✓ Választott irány** |

A gyári HA ESPHome add-on **nem** kínál kattintgatós, kód nélküli eszköz-létrehozást – a motorháztető alatt mindig YAML van.

---

## Választott flotta-architektúra (3. megoldás)

### Üzembe helyezési folyamat (seamless provisioning)

```
Műhely                    Helyszín (szerelő)              Központi szerver
──────                    ──────────────────              ────────────────
HW összeszerelés    →     Áram alá helyezés        →     (várakozás)
ESPHome flash              Captive Portal Wi-Fi
(generikus YAML)           SSID + jelszó
MAC-alapú MQTT ID    →     Online                  →     TB: új / unpárosított eszköz
                                                      →     Szerelő: Customer / Asset / Device assign
                                                      →     Ügyfél dashboard: widget megjelenik
```

### Lépések részletesen

| Lépés | Hol | Mi történik |
|-------|-----|-------------|
| 1. Gyártás | Műhely | Egyedi NYÁK; ESPHome flash **generikus** konfiggal: pinout, `captive_portal`, MQTT broker, **MAC-alapú azonosító** (pl. `esp32-a1b2c3d4`) |
| 2. Wi-Fi | Helyszín | Szerelő: hotspot → helyszíni Wi-Fi |
| 3–4. Regisztráció | ThingsBoard admin | Customer → Asset (ház) → Asset (szoba) → Device assign + elnevezés – **csak TB metaadat** |
| 5. Dashboard | ThingsBoard | Widgetek a telemetriából / shared attributes-ből |

### Miért jó ez a modell?

- Szerelőnek **nincs** laptop, YAML, fordítás
- Eszköz áthelyezhető / letiltható **adatbázisból**, helyszíni beavatkozás nélkül
- Eszközök különböző hálózatok mögött – **MQTT outbound** elegendő, VPN nem kell minden ügyfélhez
- Firmware **egyszer** készül típusonként; hierarchia és név a **szerveren** él

### Generikus ESPHome konfiguráció (flottához)

A műhelyben feltöltött szoftver tartalma:
- Hardveres lábkiosztás (szenzor típus szerint)
- `captive_portal` Wi-Fi beállításhoz
- MQTT komponens központi brokerre (EMQX)
- Eszközazonosító: **ESP MAC cím** (gyári, egyedi)
- **Nincs** fix user név, ház, szoba a firmware-ben

---

## Szerver oldali felépítés

→ Részletes dokumentáció: [`thingsboard-dontes.md`](thingsboard-dontes.md)

### Összefoglaló

| Komponens | Technológia | Megjegyzés |
|-----------|-------------|------------|
| IoT platform | **ThingsBoard** | Dashboard, device mgmt, FOTA, multi-tenant |
| MQTT | TB beépített **vagy** EMQX | Döntendő |
| Firmware toolchain | ESPHome CLI + CI/CD | Csak fejlesztés/gyártás – nem éles szerver |
| Home Assistant | Nem kell | – |
| Saját FastAPI | Opcionális | LLM, speciális üzleti logika – ha kell |

### Utólagos konfiguráció (ThingsBoard)

| Szint | Mikor | Hogyan |
|-------|-------|--------|
| **1. Paraméterek** | Napi (határérték, időzítés) | Shared Attribute / RPC → ESPHome `number` → NVS |
| **2. FOTA** | Strukturális YAML változás | `.bin` feltöltés TB-be → csoportos OTA |
| **3. Sablon pipeline** | Tömeges firmware frissítés | GitHub → CI/CD → TB REST API |

### Mit **nem** kell saját fejlesztésben (ThingsBoard-bal)

- Saját MQTT→DB worker, FOTA infra, multi-tenant auth alapréteg, dashboard framework

### ESPHome fordítás hol történik?

| Fázis | Hol | Eszköz |
|-------|-----|--------|
| Fejlesztés | Fejlesztő gép / CI / ESPHome Docker | `esphome compile` → `.bin` |
| Gyártás | Műhely | Ugyanaz a `.bin` → 100–10 000 darab |
| Éles üzem | – | **Nincs** ESPHome a szerveren |

Hardveres funkció bővítésekor: sablon YAML frissítés → új `.bin` → OTA (2. fázis) vagy műhelyben újraflash.

---

## Kapcsolat a meglévő SmartBlue döntésekkel

| Terület | Eddigi döntés | ESPHome irány hatása |
|---------|---------------|----------------------|
| MQTT Broker | EMQX vagy TB beépített | Döntendő |
| Backend | ThingsBoard (volt: FastAPI) | Felülvizsgálat |
| Dashboard | ThingsBoard | Felülvizsgálat |
| Topic névkonvenció | MAC-suffix, firmware-agnosztikus DB név | **Kompatibilis** – MAC továbbra is kulcs |
| Tasmota `cmnd/stat/tele` | Döntve | ESPHome saját topic struktúra → protokoll doksi frissítés |
| Teszt (D1 Mini + Tasmota) | Sikeres | Megtartva referenciaként; ESPHome pilot szükséges |
| Tasmota Manager desktop app | Kész | ESPHome esetén más tooling (CLI, web.esphome.io, saját API) |
| 1. fázis scope | Adatgyűjtés + dashboard | Változatlan; firmware váltás nem blokkolja |

---

## Nyitott kérdések és következő lépések

### Döntendő

- [ ] **Hivatalos firmware döntés** – ESPHome megerősítése a csapattal (Viktor, Zsolti, Bálint)
- [ ] **ESPHome MQTT topic séma** – SmartBlue konvenció definiálása (`mqtt-protokoll.md`)
- [ ] **Generikus flotta YAML** – első eszköztípus (pl. jelenlét + hőmérséklet) sablon
- [ ] **EMQX auth** – MAC-alapú eszköz hitelesítés ESPHome-nál
- [ ] **ThingsBoard pilot** – teljes 5 fázis → [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)

### Fejlesztési roadmap (2. fázis kapcsolódó)

- [ ] Szerelői provisioning UX ThingsBoard-ban (unassigned devices)
- [ ] OTA frissítés központilag (sablon verzióváltás)
- [ ] MQTT biztonság – hamis eszközök kiszűrése
- [ ] Távoli parancs (vezérlés) MQTT-n keresztül

### További vizsgálandó

- Improv Wi-Fi vs Captive Portal szerelői UX
- Captive Portal jelszóvédelem
- Wi-Fi jelszó változás → hotspot kényszerítés
- ESPHome Safe Mode hibás Wi-Fi konfig esetén
- Bluetooth proxy (csak ESPHome + HA – SmartBlue-nál valószínűleg nem releváns)
- GSM adatkapcsolat: ESPHome gyárilag nem támogatja – lásd [GSM szekció](#gsm-kommunikáció--esphome-korlátok)
- LoRa: Packet Transport pilot – Heltec gateway + távoli node

---

## Források

- [ESPHome – WiFi komponens](https://esphome.io/components/wifi.html) – Captive Portal, több hálózat
- [web.esphome.io](https://web.esphome.io) – böngészős első flash
- Meglévő projekt doksi: [`hw-d1mini-tasmota.md`](hw-d1mini-tasmota.md), [`thingsboard-dontes.md`](thingsboard-dontes.md)
