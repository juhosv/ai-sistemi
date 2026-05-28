# Kijelzők – ESP32 / Tasmota kompatibilis opciók

---

## Tasmota kijelző támogatás – áttekintés

| Típus | Tasmota | Megjegyzés |
|-------|---------|------------|
| **SSD1306 OLED I2C** | ✓ Natív | Legjobb kezdő választás, 4 vezeték |
| **SH1106 OLED I2C** | ✓ Támogatott | SSD1306 alternatíva |
| I2C LCD 1602 / 2004 | ✓ Támogatott | Nagyobb karakteres kijelzőhöz |
| ILI9341 / ILI9488 TFT SPI | ✓ Támogatott | Több GPIO, több konfiguráció |
| Waveshare e-paper | ✓ Bizonyos típusok | Ritkán frissülő kijelzőkhöz |

> **Fontos:** Kijelzőhöz nem feltétlenül elegendő a `tasmota32.bin`.  
> Szükséges build: **`tasmota32-display.bin`** vagy uDisplay-t tartalmazó build.  
> Az uDisplay (Universal Display Driver) ESP32 és ESP8266 precompiled binárisokban benne van, Option A3 GPIO-funkcióval + display descriptorral engedélyezhető.

---

## Ajánlott: 0.96″ SSD1306 OLED I2C (128×64)

**Bekötés (4 vezeték):**
```
VCC → 3.3V vagy 5V (modultól függően)
GND → GND
SCL → ESP32 I2C SCL GPIO
SDA → ESP32 I2C SDA GPIO
```

**Tasmota konfiguráció:**
```
GPIO_SDA → I2C SDA
GPIO_SCL → I2C SCL
I2C cím:   0x3C (vagy 0x3D)
Display:   SSD1306 / Universal Display
```

**Hestore termék:** D096-12864-I2C – ~900–1000 Ft nettó

---

## ESP32 + OLED integrált board

### Hestore: ESP-WROOM32 + 0.96″ OLED (prod_10048022)

| Paraméter | Érték |
|-----------|-------|
| MCU | ESP32-WROOM-32 |
| Flash | 4 MB (32 Mbit) |
| USB | USB-C, CH340 |
| OLED | 0.96″, 128×64, sárga-kék |
| OLED driver | SSD1306 (Hestore adatlapján „SSD106" – valószínűleg elírás) |
| OLED I2C cím | 0x3C |
| OLED SDA | GPIO21 |
| OLED SCL | GPIO22 |
| Ár | ~3 116 Ft nettó |
| Raktár | >100 db |

**Tasmota irány:** `tasmota32-display.bin` vagy uDisplay build

**Értékelés:**
- Tesztelésre / prototípushoz: ✓ jó vétel (1 db)
- Tömeges gyártáshoz: ✗ drágább – inkább külön ESP32 + külön SSD1306 modul (~1692 + ~900 Ft = olcsóbb, rugalmasabb)

**Felhasználás a ventilátor-szabályozóban:**
```
Temp: 36.4 C
Fan:  45 %
Mode: AUTO
Sensor: OK
```

---

## Kijelző összehasonlítás – mikor mit válassz

| Kijelző | Mikor érdemes |
|---------|---------------|
| SSD1306 0.96″ I2C | Státusz / hőmérséklet / PWM kijelzés, egyszerű projektek |
| SSD1306 0.91″ I2C | Kis helyen, pl. kapcsolódobozban |
| I2C LCD 1602 | Több soros szöveges adat, olvashatóbb kisbetű |
| ILI9341 TFT | Grafikus UI, több adat, de több munka |
| E-paper | Ritkán frissülő kijelzés, pl. névtábla, műszak lista |
