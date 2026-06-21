# Alkatrész beszerzések

---

## Hestore – 2026-05-28

Forrás: `hestore_20260528.xml`

### Mikrokontrollerek / fejlesztői modulok

| Cikkszám | Leírás | db |
|----------|--------|----|
| D1-MINI-V4.0.0 | D1 Mini, ESP8266, 4MB, TYPE-C USB, CH340 | 1 |
| ESP-WROOM32-CH340-USB-C | ESP-WROOM-32, WiFi+BT, CH340, USB-C | 1 |
| ESP32-C3-SUPERMINI | ESP32-C3 Super Mini, 4MB Flash, RISC-V 160MHz | 1 |
| ESP32-C3-SUPERMINI-EXP | ESP32-C3 Super Mini kifejtő panel | 1 |
| ESP32-S3-DEV-N16R8 | ESP32-S3, 16MB flash, 8MB PSRAM, dual-core LX7 240MHz | 1 |
| ESP32-D1-MINI-CP2104-C | D1 Mini formátumú ESP32, CP2104, USB-C, WeMos kiosztás | 1 |
| WEMOS-D1-MINI-PRO | WeMos D1 Mini Pro, ESP8266, 16MB, uFL antenna, microUSB | 1 |
| ESP32-DEVKIT-32UE-4M | ESP32-WROOM-32UE, 4MB, UFL antenna, dual core, CP2102 | 1 |
| ESP32-DEVKIT-32U-4M | ESP32-WROOM-32U, 4MB, UFL antenna, dual core, CP2102 | 1 |

### Kiegészítők

| Cikkszám | Leírás | db |
|----------|--------|----|
| ESP32S-TA-38P | Kifejtő adapter, 38 pólusú, ESP32-höz | 1 |
| uFL-SMA + ANT | RF kábel UFL–SMA female + SMA male WiFi antenna 3dBi | 2 |

### Szenzorok

| Cikkszám | Leírás | db |
|----------|--------|----|
| GY-BME280-3.3V | BME280 – hőmérséklet, páratartalom, légnyomás, I2C, 3.3V | 1 |
| GY-302 | BH1750 – fényérzékelő (lux), I2C | 1 |
| DS18B20-1M | DS18B20 vízhatlan hőmérő szonda, 1m | 1 |

### Megjegyzések

- Az **uFL antennás** ESP32 modulok (32UE, 32U, Mini Pro) külső antennával jobb lefedettséget adnak – hasznos terepi / falon kívüli telepítésnél
- Az **ESP32-C3** RISC-V architektúrájú (nem Xtensa) – Tasmota támogatás ellenőrizendő
- Az **ESP32-S3** a legteljesebb ebben a csomagban (16MB flash, 8MB PSRAM, 240MHz dual-core)
- A **BME280 3.3V-os modul** – ne adj rá 5V-ot

---

## Tervezett / vizsgált alkatrészek (nem megvett)

### Kijelzők

| Hestore termék | Leírás | Tasmota | Megjegyzés |
|----------------|--------|---------|------------|
| D096-12864-I2C | 0.96″ SSD1306 OLED 128×64, I2C | ✓ | ~900–1000 Ft, legjobb kezdő kijelző |
| prod_10048022 | ESP32-WROOM-32 + 0.96″ OLED integrált board | ✓ (display build) | 3 116 Ft nettó, tesztelésre jó |

### Ethernet ESP32

| Hestore termék | Leírás | Mikor érdemes |
|----------------|--------|---------------|
| prod_10047946 | WT32-ETH01 – ESP32 + RJ45 Ethernet | Fix telepítésű eszközökhöz, ahol nincs megbízható WiFi (kazánház, gépészet, szerverrack) |

> **WT32-ETH01 megjegyzések:**
> - Nettó ~6 267 Ft (drágább mint sima ESP32)
> - Az Ethernet chip több GPIO-t lefoglal
> - Nincs beépített USB programozó → külső USB–TTL adapter kell flasheléshez
> - Tasmotával/ESPHome-mal használható, de első körre nem ez az ajánlott fejlesztői board

### Talaj szenzor (többparaméteres)

> **Igény (2026-06-21):** nem elég a kapacitív nedvesség-sonda – **nedvesség + hőmérséklet + EC** minimum.

#### Hestore összehasonlítás (2026-06-21)

| Hestore | Termék | Mér | Ár (1+ db, nettó) | Raktár | Javaslat |
|---------|--------|-----|------------------|--------|----------|
| [prod_10048070](https://www.hestore.hu/prod_10048070.html) | **SOIL-H-T-EC-RS485** | Nedvesség, hőmérséklet, EC (+ só, TDS Modbus reg.) | **12 333 Ft** | > 5 | **Ajánlott – megvenni** |
| [prod_10048071](https://www.hestore.hu/prod_10048071.html) | SOIL-H-RS485 | Csak nedvesség | 10 461 Ft | > 10 | ❌ Nem elég – csak 1 paraméter |
| [prod_10046391](https://www.hestore.hu/prod_10046391.html) | JXBS-3001-NPK-RS | 7-in-1: NPK + pH + EC + hő + nedvesség | 37 463 Ft | > 5 | Drágább; NPK/pH pontossága kérdéses |

**Ajánlott vásárlás:** `SOIL-H-T-EC-RS485` (cikkszám 100.480.70)

| Paraméter | Tartomány | Pontosság |
|-----------|-----------|-----------|
| Talajnedvesség | 0…100 %RH | ±2 % (0–50 %), ±3 % (50–100 %) |
| Talaj hőmérséklet | −40…+80 °C | ±0,5 °C |
| EC (vezetőképesség) | 0…20 000 µS/cm | ±3 % (0–10 000 µS/cm) |

**Technikai adatok:**
- IP68, rozsdamentes acél szonda, 2 m kábel
- Táp: 5…30 V DC (max. 0,5 W @ 24 V)
- RS485 Modbus-RTU, alap baud: **4800**
- Kivezetés: Barna V+, Fekete GND, Kék RS485_B, Sárga RS485_A
- Modbus regiszterek: `0x0000` nedvesség, `0x0001` hőmérséklet, `0x0002` EC, `0x0003` só, `0x0004` TDS

**Kiegészítő modul (ESP32-hez):**

| Hestore | Termék | Ár (1+ db, nettó) | Raktár | Megjegyzés |
|---------|--------|-------------------|--------|------------|
| [prod_10035508](https://www.hestore.hu/prod_10035508.html) | **MAX485-M** RS485–TTL | **365 Ft** | > 500 | **Megvenni** – talaj szonda illesztéséhez |
| [prod_10047988](https://www.hestore.hu/prod_10047988.html) | USB-RS485 (CH340) | 613 Ft | > 350 | Asztali teszteléshez (PC ↔ szonda) |

> Tasmota: RS485 Modbus olvasás egyedi megoldást igényel (Serial + Modbus parancs, vagy custom driver). Baud: 4800, 8N1.

---

### Jelenlét érzékelő (nem PIR)

> **Igény (2026-06-21):** **jelenlét érzékelő** kell, **nem mozgásérzékelő** (PIR). Statikus ember is érzékelendő.

#### Hestore – LD2410C (2026-06-21)

| Hestore | Termék | Ár (1+ db, nettó) | Raktár | Javaslat |
|---------|--------|-------------------|--------|----------|
| [prod_10046482](https://www.hestore.hu/prod_10046482.html) | **LD2410C** – emberi jelenlét radar (Hi-Link) | **1 806 Ft** | > 250 | **Megvenni** |

**LD2410C technikai adatok:**
- 24 GHz FMCW mmWave radar – mozgó **és** álló ember érzékelése (mikromozgás)
- Hatótáv: 0,75…6 m, látószög 60°
- Kimenet: **GPIO** (van/nincs jelenlét) + **UART** (távolság, állapot protokoll)
- UART: 256000 baud, 8N1; IO szint 3,3 V; táp **5 V DC** (> 200 mA)
- Bluetooth + vizuális konfigurációs eszköz (érzékenység, távolság zónák)
- Beltéri használatra (fólia sátor / szoba is jó)

> A Hestore-n csak LD2410**C** van készleten (nem a régebbi LD2410). Tasmota: GPIO Switch bemenet egyszerűen; UART adatokhoz egyedi Serial parser kell.

> A meglévő PIR teszt (D1 Mini) marad referenciának, de új beszerzésnél LD2410C a cél.

---

### Tervezett kosár összesítés (Hestore, 2026-06-21)

| Termék | db | Egységár (nettó) | Összesen |
|--------|----|------------------|----------|
| SOIL-H-T-EC-RS485 | 1 | 12 333 Ft | 12 333 Ft |
| MAX485-M | 1 | 365 Ft | 365 Ft |
| LD2410C | 1 | 1 806 Ft | 1 806 Ft |
| **Összesen** | | | **~14 504 Ft** |

Opcionális: USB-RS485 (613 Ft) – szonda PC-s teszteléshez a firmware fejlesztés alatt.
