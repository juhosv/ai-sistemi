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
