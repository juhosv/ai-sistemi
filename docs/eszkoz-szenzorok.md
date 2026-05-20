# ESP32 Szenzor Katalógus

> Referencia a SmartBlue eszközcsalád lehetséges szenzoraihoz.  
> A lista a pilot fázis egyszerűbb szenzoraitól a haladó / „profi IoT" szintig terjed.

---

## 🌡️ Alap környezeti szenzorok (pilot fázis)

| Szenzor | Mér | Megjegyzés |
|---------|-----|------------|
| DHT22 | Hőmérséklet, páratartalom | Egyszerű, 1-wire, népszerű |
| BMP280 / BME280 | Hőmérséklet, légnyomás, (páratartalom) | I2C/SPI, pontosabb mint DHT22 |
| DS18B20 | Hőmérséklet | 1-wire, vízálló változat is létezik |

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

## 👀 Mozgás és jelenlét

### PIR-nél okosabb megoldások

| Szenzor | Technológia | Előny |
|---------|-------------|-------|
| **LD2410** | mmWave radar (24 GHz) | Statikus embert is érzékel (nem csak mozgást) |
| **RCWL-0516** | Mikrohullámú Doppler radar | Fal / üveg mögött is érzékel, olcsó |

> **LD2410 vs PIR:** A PIR csak mozgást érzékel. Az LD2410 légzés / szívverés szintű mikromozgást is – valaki ülve, olvasva is „jelenlét".

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
| Kapacitív talajnedvesség | Talaj nedvességtartalom | Növényöntözés automatika |
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
| Jelenlét / mozgásérzékelő | LD2410 (mmWave), APDS-9960 |
| Energiafogyasztás mérő | INA219 (DC) vagy SCT-013 (AC) |
| Növénymonitor | Talajnedvesség + DHT22 + fényszenzor |
| Általános I/O (relé + szenzor) | BME280 + relékimenet |

---

## Nyitott kérdések

- [ ] Melyik szenzortípusok kerülnek bele az **első pilot**ba?
- [ ] Szükséges-e CO₂ mérés a pilot helyszíneken?
- [ ] LoRa érdekes lehet-e a GSM helyett egyes terepi helyszíneken?
