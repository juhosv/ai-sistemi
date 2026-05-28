# Projekt: Hőmérsékletfüggő ventilátor-szabályozó

> **Státusz:** Ötlet / tervezés fázis  
> **Platform:** ESP32 + Tasmota (vagy ESPHome)  
> **Szerver:** Opcionális – az alapfunkció önállóan is működik

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

## Tasmota konfiguráció

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

Az ESP32 + Tasmota Rules **Home Assistant / MQTT broker nélkül** is tud önállóan szabályozni:
- Webes felületen (helyi IP-n) állítható a logika
- WiFi-n keresztül elérhető, de internet nem szükséges

| Funkció | Szerver nélkül |
|---------|----------------|
| Automatikus ventilátorszabályozás | ✓ Igen |
| Helyi webes beállítás | ✓ Igen |
| Hosszú távú naplózás / grafikon | ✗ Nincs |
| Mobilos dashboard | ✗ Korlátozott |
| MQTT integráció a SmartBlue szerverrel | ✓ Opcionálisan hozzáadható |

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
| Finom / lineáris / PID vezérlés | Nehézkes | ✓ Natív PID controller |
| Konfigurálás módja | Webfelület / MQTT | YAML fordítás |
| Szerver nélküli működés | ✓ | ✓ |
| SmartBlue MQTT integrálhatóság | ✓ Natív | ✓ |

---

## Nyitott kérdések

- [ ] 2 vagy 4 vezetékes ventilátor?
- [ ] Lépcsős Tasmota Rules elegendő, vagy PID (ESPHome)?
- [ ] Milyen alkalmazásba kerül? (szerverrack, ipari szekrény, 3D nyomtató, egyéb?)
- [ ] Szükséges-e SmartBlue szerver integráció (naplózás, riasztás)?
