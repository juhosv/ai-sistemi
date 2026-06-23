# Projekt: Hőmérsékletfüggő ventilátor-szabályozó

> **Státusz:** Ötlet / tervezés fázis  
> **Platform:** ESP32 + ESPHome (valószínű) + ThingsBoard  
> **Szerver:** ThingsBoard dashboard – user állíthatja a PWM határértékeket csúszkával  
> **Részletes minta:** [`thingsboard-dontes.md`](thingsboard-dontes.md#példa-hőmérséklet--pwm-szabályozás-felhasználói-csúszkákkal)  
> **Megvalósítási lépések:** [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)

---

## Két vezérlési út

| Típus | Hardver | ESPHome komponens | Mikor |
|-------|---------|-------------------|-------|
| **DC ventilátor** | MOSFET + 12/24 V | `ledc` PWM | PC venti, alacsony feszültség |
| **AC ventilátor** | Triak + nullátmenet + optocsatoló | **`ac_dimmer`** | Hálózati (230 V) fázishasításos vezérlés |

---

## Koncepció

```
DS18B20 / BME280
       │ hőmérséklet adat
       ▼
   ESP32 + Tasmota
   (PWM kimenet szabályozva)
       │ PWM jel (GPIO)
       ▼
   MOSFET illesztő
       │ vezérelt áram
       ▼
   Ventilátor (12V / 24V DC)
```

---

## Szenzorválasztás

| Szenzor | Mikor válaszd |
|---------|---------------|
| **DS18B20 vízhatlan** | Konkrét tárgy / cső / hűtőborda / szekrény belseje hőmérséklete |
| **BME280** | Környezeti levegőhőmérséklet + páratartalom + légnyomás |
| DHT22 | Kerülendő ennél a projektnél – lassabb, nyűgösebb |

---

## Hardver kapcsolás

### AC ventilátor – Triak + nullátmenet (230 V) – ESPHome `ac_dimmer`

Hálózati ventilátoroknál **nem** elég szoftveres PWM: kell **nullátmenet-érzékelés** (zero-cross) és **fázishasításos** triak gyújtás. Az ESPHome **`ac_dimmer`** komponense ezt **natívan** kezeli – C++ interrupt kód nélkül.

```
230 V AC ──── Triak ──── Ventilátor (AC)
                ▲
         gate_pin (GPIO23) ← optocsatoló (pl. MOC3021)
                │
         ESP32 ac_dimmer
                │
    zero_cross_pin (GPIO25) ← nullátmenet-érzékelő áramkör
```

| Láb | Szerep |
|-----|--------|
| `zero_cross_pin` | Hálózat nullátmenetének figyelése – 50 Hz → ~10 ms félperiódus |
| `gate_pin` | Triak gyújtóimpulzus, késleltetéssel (fázishasítás) |
| `method: leading pulse` | Triakhoz kötelező – rövid gyújtótüske |

**Működés (háttérben):** az ESPHome automatikusan számolja a hálózati frekvenciát, mikroszekundumos pontossággal adja a gyújtóimpulzust – hasonlóan a RobotDyn AC Dimmer modulokhoz.

**Processzor:** **ESP32 javasolt** (nem ESP8266) – kétmagos; a nullátmenet időzítés stabilabb MQTT/Wi-Fi forgalom mellett is (ESP8266-nál mikroszekundumos késés → fordulatszám-ingadozás).

### 2 vezetékes DC ventilátor (N-MOSFET low-side)

```
12V+  ─────────────── Ventilátor (+)
Ventilátor (−) ─────── MOSFET Drain
MOSFET Source ─────── GND
ESP32 GND ──────────── 12V táp GND     ← közös GND kötelező!
ESP32 PWM GPIO ──── [gate ellenállás] ── MOSFET Gate
                                    └── [100kΩ lehúzó] ── GND
```

**MOSFET követelmény:** logikai szintű N-MOSFET (3.3V gate-nél is teljesen nyit)  
Pl.: IRLZ44N, IRL520N, AO3400

### 4 vezetékes PC ventilátor (25 kHz PWM)

- Fix 12V táp a ventilátornak
- Külön PWM vezérlőbemenet (4. ér)
- A PC ventilátor PWM frekvenciája ~25 kHz – ellenőrizd az adatlapot
- Illesztés: open-drain MOSFET vagy tranzisztor (ne közvetlenül GPIO-ból!)

---

## ESPHome – komplex helyi logika (AC Triak)

A hőmérséklet → teljesítmény szabályozás **100%-ban lokálisan** fut (offline is). A ThingsBoard a **határértékeket** és a **fordulatszám-tartományt** állítja; a triak/PWM időzítés a chipen marad.

### Szabályozási paraméterek

| ESPHome `number` | Alapérték | Tartomány | Jelentés |
|------------------|-----------|-----------|----------|
| `also_hatar` | (telepítéskor) | 10–40 °C | Alsó hőmérséklet – e felett indul a szabályozás |
| `felso_hatar` | (telepítéskor) | 20–60 °C | Felső hőmérséklet – e felett max. fordulat |
| `min_fordulat` | **20 %** | 0–100 % | Minimális fordulatszám / teljesítmény (szabályozás közben) |
| `max_fordulat` | **100 %** | 0–100 % | Maximális fordulatszám / teljesítmény |

**Számítási logika:**

1. `t ≤ also_hatar` → kimenet **0 %** (ventilátor ki)
2. `also_hatar < t < felso_hatar` → lineáris: **min_fordulat** … **max_fordulat** között
3. `t ≥ felso_hatar` → kimenet **max_fordulat**

```
Teljesítmény %
max_fordulat ─────────────────●────────  (100% default)
              ╱
min_fordulat ●                          (20% default)
            ╱
    0 % ───●──────────────────────────
         also_hatar    felso_hatar     → Hőmérséklet °C
```

### YAML – `ac_dimmer` + lambda (hőmérséklet alapú)

```yaml
output:
  - platform: ac_dimmer
    id: triak_kimenet
    gate_pin: GPIO23
    zero_cross_pin: GPIO25
    method: leading pulse

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
              id: triak_kimenet
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

number:
  - platform: template
    name: "also_hatar"
    id: also_hatar
    min_value: 10
    max_value: 40
    step: 1
    optimistic: true
    restore_value: true

  - platform: template
    name: "felso_hatar"
    id: felso_hatar
    min_value: 20
    max_value: 60
    step: 1
    optimistic: true
    restore_value: true

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

### DC ventilátor esetén

Ugyanaz a lambda és a négy `number` paraméter; `output: platform: ledc` az `ac_dimmer` helyett (lásd [`thingsboard-megvalositas.md`](thingsboard-megvalositas.md)).

> **AC ventilátor:** a korábbi fix 15% minimum helyett a **`min_fordulat`** (default 20%) állítható – búgás / túl alacsony feszültség elkerülésére.

### Mi marad MQTT-n kívül?

A triak nullátmenet-időzítés, a lambda számítás és a `restore_value` logika **100% lokális** – lásd [`mqtt-protokoll.md`](mqtt-protokoll.md#esphome--thingsboard-ce--mqtt-architektúra).

### ThingsBoard és szerelő – változatlan folyamat

| Réteg | Változik? |
|-------|-----------|
| Szerelő: Captive Portal Wi-Fi | Nem |
| TB: `also_hatar` / `felso_hatar` csúszkák | Nem |
| TB: **`min_fordulat` / `max_fordulat`** csúszkák | Új widgetek |
| TB: `Belso Homerseklet` telemetria | Nem |
| TB: opcionális `Ventilator_Teljesitmeny` | Új – élő % visszajelzés |
| Triak / PWM időzítés | **Csak ESPHome-ban** |

→ [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md) – egyedi logika lambdákkal, interrupt nélkül

---

## Tasmota konfiguráció (legacy / referencia)

### GPIO lábak

```
GPIO_x → DS18B20 (1-Wire) vagy I2C SDA/SCL (BME280)
GPIO_y → PWM kimenet (ventilátor vezérlés)
```

> ESP32-n a PWM hardveres LEDC alapú, akár 16 csatorna, tetszőleges frekvencia.  
> A 4.7 kΩ felhúzóellenállás a DS18B20 adatvonalán kötelező.

### Tasmota Rules – lépcsős vezérlés

```
Rule1
  ON DS18B20#Temperature<30 DO PWM1 0 ENDON
  ON DS18B20#Temperature>=30 DO PWM1 255 ENDON
  ON DS18B20#Temperature>=35 DO PWM1 512 ENDON
  ON DS18B20#Temperature>=40 DO PWM1 1023 ENDON
Rule1 1
```

Finomabb szabályozás vagy PID-szerű vezérlés esetén → **ESPHome** javasolt (szebb YAML szintaxis, beépített PID controller).

### Lépcsős logika (tervezési alap)

| Hőmérséklet | Ventilátor |
|-------------|-----------|
| < 30°C | 0% (ki) |
| 30–35°C | ~25% |
| 35–40°C | ~60% |
| > 40°C | 100% |

---

## Önálló működés (szerver nélkül)

Az ESP32 + ESPHome lambda / `ac_dimmer` **ThingsBoard nélkül** is szabályoz – `restore_value: true` miatt a határértékek áramszünet után is megmaradnak.

| Funkció | Szerver nélkül |
|---------|----------------|
| Automatikus ventilátorszabályozás (DC PWM vagy AC triak) | ✓ Igen |
| Nullátmenet / fázishasítás | ✓ `ac_dimmer` |
| Hosszú távú naplózás / grafikon | ✗ Nincs |
| ThingsBoard dashboard + csúszkák | ✗ Korlátozott |
| MQTT → ThingsBoard | ✓ Opcionálisan |

---

## Fail-safe szempontok (biztonságkritikus alkalmazásnál)

- Szenzorhiba → ventilátor **100%** (inkább fölöslegesen hűt, mint nem hűt)
- Túl magas hőmérséklet → ventilátor **100%**
- ESP újraindulás utáni alapállapot: **biztonságos / maximális hűtés**
- MOSFET és tápegység: **túlméretezés** (x1.5–2× névleges áram)
- Mechanikus / elektronikus hővédelem a szabályozott eszközben is

---

## Tasmota vs ESPHome

| Szempont | Tasmota | ESPHome |
|---------|---------|---------|
| Egyszerű lépcsős szabályozás | ✓ Jó | ✓ Jó |
| Finom / lineáris vezérlés | Nehézkes | ✓ Lambda |
| **AC triak + nullátmenet** | Korlátozott | ✓ **`ac_dimmer` natív** |
| PID vezérlés | Nehézkes | ✓ Beépített PID |
| Konfigurálás | Webfelület / MQTT | YAML + OTA |
| ThingsBoard integráció | MQTT | MQTT |
| Offline helyi logika | Rules | Lambda + `restore_value` |

---

## Opcionális: OLED kijelző hozzáadása

Helyi státuszkijelző hozzáadható – szerver / Home Assistant nélkül is látható az állapot:

```
Temp: 36.4 C
Fan:  45 %
Mode: AUTO
Sensor: OK
```

**Ajánlott:** 0.96″ SSD1306 I2C OLED (128×64)
- Csak 2 extra GPIO (SDA + SCL, I2C-n a szenzorral megosztható!)
- Tasmota build: `tasmota32-display.bin` szükséges
- Hestore opció: `D096-12864-I2C` (~900–1000 Ft) vagy integrált ESP32+OLED board (~3 116 Ft)

→ Részletek: [`hw-kijelzok.md`](hw-kijelzok.md)

## Távolról paraméterezhető működés (SmartBlue integráció)

> Megbeszélés alapján (2026-06-07): a helyszíni újrakonfigurálás elkerülése kulcsfontosságú.

### Mit lehet távolról látni
- Aktuális hőmérséklet (DS18B20 / BME280 / DHT)
- Aktuális ventilátor teljesítmény / PWM % (opcionális MQTT telemetria: `Ventilator_Teljesitmeny`)
- Üzemállapot (fut / leállt / hiba)
- Riasztás: ha a hőmérséklet küszöb felett van, de a ventilátor nem fut

### Mit lehet távolról beállítani (ThingsBoard)

A hőmérséklet–teljesítmény görbe **határértékei** Shared Attribute / RPC-n keresztül:

| TB mező | ESPHome `number` | Alapérték | Hatás |
|---------|------------------|-----------|-------|
| `also_hatar` | Alsó hőmérséklet | – | Szabályozás indulási pontja (°C) |
| `felso_hatar` | Felső hőmérséklet | – | Max. fordulat hőmérsékleti pontja (°C) |
| `min_fordulat` | Min. fordulatszám | **20 %** | Legalacsonyabb teljesítmény szabályozás közben |
| `max_fordulat` | Max. fordulatszám | **100 %** | Legmagasabb teljesítmény |

A **fázishasításos / PWM időzítés** nem a szerveren fut – csak a fenti négy paraméter változik távolról.

→ Korábbi Tasmota `Mem` + Rules megközelítés: legacy referencia alább.

<details>
<summary>Tasmota Mem változók (legacy)</summary>

```
cmnd/{topic}/Mem1  →  alsó küszöb (°C)
cmnd/{topic}/Mem2  →  felső küszöb (°C)
cmnd/{topic}/Mem3  →  minimális PWM %
```

</details>

---

## Opcionális: Ethernet (WiFi helyett)

Fix telepítésű eszközöknél (kazánház, gépészeti szekrény, szerverrack) érdemes lehet:

**WT32-ETH01** (Hestore prod_10047946): ESP32 + RJ45 Ethernet, ~6 267 Ft nettó

```
DS18B20 → WT32-ETH01 → Ethernet kábel → helyi hálózat → SmartBlue szerver
                ↓
           PWM GPIO → MOSFET → ventilátor
```

> Ha a szabályozás önállóan fut (Tasmota Rules), az Ethernet csak monitoringhoz / konfighoz kell.

---

## Nyitott kérdések

- [ ] **DC (MOSFET/PWM) vagy AC (triak + `ac_dimmer`)?**
- [ ] 2 vagy 4 vezetékes DC ventilátor?
- [ ] Lépcsős logika elegendő, vagy lineáris lambda / PID?
- [ ] Milyen alkalmazás? (szerverrack, ipari szekrény, 3D nyomtató, hálózati venti)
- [ ] AC minimum teljesítmény – **`min_fordulat`** default 20%, hangolható TB-ről
- [ ] Kell-e helyi OLED kijelző?
- [ ] WiFi elegendő, vagy Ethernet (WT32-ETH01)?
- [ ] **230 V biztonság:** szerelői minősítés, tokozás, galvanikus elválasztás (MOC3021)
