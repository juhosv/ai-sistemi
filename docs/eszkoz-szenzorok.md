# ESP32 Szenzor Katalógus

> Referencia a SmartBlue eszközcsalád lehetséges szenzoraihoz.  
> A lista a pilot fázis egyszerűbb szenzoraitól a haladó / „profi IoT" szintig terjed.

---

## 🌡️ Alap környezeti szenzorok (pilot fázis)

| Szenzor | Mér | Tasmota | Megjegyzés |
|---------|-----|---------|------------|
| **BME280** | Hőmérséklet, páratartalom, légnyomás | ✓ Natív | I2C, 3.3V modul, legjobb általános szobaszenzor |
| **DS18B20** | Hőmérséklet | ✓ Natív (DS18x20) | 1-Wire, vízhatlan változat, több szenzor egy GPIO-n, kell 4.7kΩ felhúzó |
| **BH1750 / GY-302** | Megvilágítás (lux) | ✓ Natív | I2C, 1–65535 lux, automatizáláshoz ideális |
| DHT22 / AM2302 | Hőmérséklet, páratartalom | ✓ | Egyszerűbb, de BME280 ajánlottabb |
| BMP280 | Hőmérséklet, légnyomás | ✓ | BME280 nélküli verzió (nincs páratartalom) |

> **Ajánlott sorrend:** BME280 > DS18B20 > DHT22. A BME280 a legjobb ár/érték arányú általános szenzor.

---

## 🌫️ Levegőminőség / Környezet

### CO₂ szenzorok

| Szenzor | Elv | Jellemző |
|---------|-----|----------|
| **MH-Z19B** | NDIR infravörös | UART/PWM, önkalibrálás, 0–5000 ppm |
| **SCD41** | Fotoacusztikus NDIR | I2C, pontosabb, kompaktabb, Sensirion |

**Alkalmazás:** szellőzés vezérlés, „okos szoba", levegőminőség riasztás

### VOC / Összetett levegőminőség

| Szenzor | Mér | Megjegyzés |
|---------|-----|------------|
| **SGP40** | VOC index (illékony szerves anyagok) | I2C, Sensirion, AI-alapú index |
| **ENS160** | VOC + eCO₂ + AQI | I2C, ScioSense, beépített AI motor |

**Alkalmazás:** füstérzékelés, tisztítószer-gőz, ipari levegőminőség, „air quality index"

---

## 🌱 Talaj szenzorok

> **Igény (2026-06-21):** kell venni talaj szenzort, de **ne csak nedvességet** mérjen – több földtulajdonság együttes mérése a cél (mezőgazdasági pilot, fólia sátras termelés).

### Miért nem elég a kapacitív nedvesség-sonda?

A legolcsóbb „talajnedvesség" modulok (kapacitív v1/v2 sonda) **csak a nedvességet** adják – nincs hőmérséklet, EC, pH. Pilot és AI elemzéshez több dimenzió kell (pl. öntözés döntés + tápanyag-állapot).

### Jelölt megoldások

| Típus | Mér | Kommunikáció | Tasmota | Megjegyzés |
|-------|-----|--------------|---------|------------|
| **RS485 3-in-1 talaj szonda** | Nedvesség, talaj hőmérséklet, EC (vezetőképesség) | RS485 Modbus | ⚠ Egyedi / Modbus bridge | Ipari / mezőgazdasági standard; tartós, kalibrálható |
| **RS485 5-in-1** | Nedvesség, hőmérséklet, EC, pH, NPK | RS485 Modbus | ⚠ Egyedi | Olcsó 5-in-1 modulok pontossága gyakran kérdéses – ellenőrizendő |
| Kapacitív + DS18B20 | Nedvesség + talaj hőmérséklet (külön szonda) | Analóg + 1-Wire | ✓ Részben | Olcsó kompromisszum, de EC/pH nincs |
| pH sonda (külön) | pH | Analóg / I2C | ⚠ | Nedvesség+EC mellett kiegészítő lehet |

**Ajánlott irány:** RS485 **3-in-1** (nedvesség + hőmérséklet + EC) – ez adja a legtöbb értelmes adatot AI elemzéshez és mezőgazdasági döntésekhez anélkül, hogy csak egy paramétert mérnénk.

### Mit mérjen minimum?

| Paraméter | Miért fontos |
|-----------|--------------|
| **Talajnedvesség** | Öntözés, szikkadás, csapadék hatás |
| **Talaj hőmérséklet** | Gyökérfejlődés, fólia sátras mikroklima |
| **EC (vezetőképesség)** | Tápanyag / sótartalom proxy, trágyázás |
| pH (opcionális) | Talaj savasság – külön sonda vagy 5-in-1 |

---

## 👀 Mozgás és jelenlét

> **Igény (2026-06-21):** kell **jelenlét érzékelő**, **nem csak mozgás érzékelő** (PIR). A PIR csak mozgáskor jelez – ülő, alvó, olvasó ember „láthatatlan" marad.

### PIR vs jelenlét – döntés

| | PIR (mozgás) | mmWave jelenlét (LD2410) |
|--|--------------|---------------------------|
| Statikus ember | ❌ Nem érzékel | ✓ Érzékel (légzés szintű mikromozgás) |
| Ülő / alvó ember | ❌ | ✓ |
| Ár | Olcsó | Közepes (~1500–3000 Ft) |
| Tasmota | ✓ Switch bemenet | ✓ UART / bináris kimenet |

### PIR-nél okosabb megoldások (jelenlét)

| Szenzor | Technológia | Előny |
|---------|-------------|-------|
| **LD2410C** | mmWave radar (24 GHz) | Statikus embert is érzékel – **Hestore prod_10046482, ~1806 Ft** |
| **RCWL-0516** | Mikrohullámú Doppler radar | Fal / üveg mögött is érzékel, olcsó – de **mozgás-alapú**, nem statikus jelenlét |

> **LD2410 vs PIR:** A PIR csak mozgást érzékel. Az LD2410 légzés / szívverés szintű mikromozgást is – valaki ülve, olvasva is „jelenlét". **Beszerzési prioritás: LD2410 (jelenlét), nem PIR.**

### Távolságmérés

| Szenzor | Technológia | Pontosság |
|---------|-------------|-----------|
| **VL53L0X** | ToF lézer | ~2 m, ±3% |
| **VL53L1X** | ToF lézer (nagyobb hatótáv) | ~4 m, pontosabb |
| HC-SR04 | Ultrahang | ~4 m, olcsóbb, kevésbé pontos |

---

## 🧠 Interakció / Gesztus

| Szenzor | Képesség | Alkalmazás |
|---------|----------|------------|
| **APDS-9960** | Gesztus (fel/le/balra/jobbra), szín, közelség | Érintés nélküli vezérlés |
| **MPU6050** | 6-tengelyes IMU (gyorsulás + giroszkóp) | Dőlés, rezgés, mozgáskövetés |
| **MPU9250** | 9-tengelyes IMU (+ magnetométer) | Drón, VR, orientáció |
| Flex szenzor | Hajlítás mértéke | Okoskesztyű, ujjmozdulat |

---

## 🌍 Speciális / „Sci-fi" szenzorok

| Szenzor | Mér | Alkalmazás |
|---------|-----|------------|
| Kapacitív talajnedvesség | Talaj nedvességtartalom | Növényöntözés automatika – **csak nedvesség, nem elég** |
| **RS485 3-in-1 talaj szonda** | Nedvesség + hőmérséklet + EC | Mezőgazdasági pilot, AI elemzés – **Hestore SOIL-H-T-EC-RS485** |
| Zavarosságmérő (turbidity) | Vízminőség | Akvárium, vízszűrés, csapadék |
| **VEML6075** | UV-A + UV-B + UV index | Napvédelem, üvegház, napelem monitoring |
| pH szenzor | pH érték | Akvárium, talaj, vízkezelés |

---

## ⚡ Mérnöki / „Hacker" szenzorok

| Szenzor | Mér | Megjegyzés |
|---------|-----|------------|
| **INA219** | DC áram, feszültség, teljesítmény | I2C, ±3.2A, fogyasztásmérés |
| **SCT-013** | AC áram (nem invazív) | Lakáshálózat fogyasztásmérés, transzformátoros |
| **INMP441** | I2S mikrofon | FFT, zajszint, hangdetektálás |
| Hall szenzor | Mágneses tér | Ajtó/ablak nyitás, forgásmérés |
| **LoRa modul (SX1276/SX1278)** | Rádió (km-es hatótáv) | LPWAN, GSM nélküli terepi kommunikáció |
| 🧲 Reed relé | Mágneses közelség | Egyszerű ajtóérzékelő |

---

## SmartBlue eszközcsalád – szenzor kapcsolat

| Eszköztípus (tervezett) | Szenzor(ok) |
|-------------------------|-------------|
| Hőmérséklet / páratartalom monitor | DHT22, BME280, SCD41 |
| Levegőminőség állomás | MH-Z19B / SCD41 + SGP40/ENS160 + BME280 |
| Jelenlét / mozgásérzékelő | **LD2410** (mmWave jelenlét), APDS-9960 – **PIR helyett LD2410** |
| Energiafogyasztás mérő | INA219 (DC) vagy SCT-013 (AC) |
| Növénymonitor / talaj | RS485 3-in-1 (nedvesség + hő + EC) + fényszenzor |
| Általános I/O (relé + szenzor) | BME280 + relékimenet |

---

## Nyitott kérdések

- [ ] Melyik szenzortípusok kerülnek bele az **első pilot**ba?
- [ ] Szükséges-e CO₂ mérés a pilot helyszíneken?
- [ ] LoRa érdekes lehet-e a GSM helyett egyes terepi helyszíneken?
- [ ] **Talaj szenzor:** Hestore **SOIL-H-T-EC-RS485** (prod_10048070) + **MAX485-M** – Modbus Tasmota integráció hogyan?
- [ ] **Jelenlét érzékelő:** Hestore **LD2410C** (prod_10046482) – GPIO vs UART bekötés Tasmotával?
- [ ] RS485–TTL konverter (MAX485) szükséges a talaj szondához?
