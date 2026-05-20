# Wemos D1 Mini – Tasmota telepítés és konfiguráció

> **Szerepe a projektben:** Pilot/teszt eszköz. Az ESP32-alapú végleges eszközcsalád előtt ezen teszteljük a Tasmota + MQTT + szerver kommunikációt.

---

## Hardver

- **Panel:** Wemos D1 Mini (ESP8266 alapú)
- **Logikai szint:** 3,3 V (GPIO-kra ne adj 5 V jelet!)
- **Csatlakozás:** micro USB (adatképes kábel kell, nem csak töltő)
- **Driver:** CH340/CH341 vagy CP2102 (klónoknál)

### Pin megfeleltetés

| D1 mini pin | ESP8266 GPIO | Megjegyzés |
|-------------|--------------|------------|
| D0 | GPIO16 | Speciálisabb, deep sleep wake |
| D1 | GPIO5 | Ajánlott általános I/O |
| D2 | GPIO4 | Ajánlott általános I/O |
| D3 | GPIO0 | Boot érzékeny – kerülendő |
| D4 | GPIO2 | Boot érzékeny, beépített LED |
| D5 | GPIO14 | Ajánlott általános I/O |
| D6 | GPIO12 | Ajánlott általános I/O |
| D7 | GPIO13 | Ajánlott általános I/O |
| D8 | GPIO15 | Boot érzékeny – kerülendő |
| A0 | – | Analóg bemenet |

**Ajánlott szenzor/relé lábak:** D1, D2, D5, D6, D7  
**Kerülendő (boot érzékeny):** D3, D4, D8

---

## Tasmota telepítése

### Módszer: Tasmota Web Installer (legegyszerűbb)

**Szükséges:**
- Chrome vagy Edge böngésző (Web Serial API)
- Adatképes micro USB kábel
- CH340/CP2102 driver telepítve

**Lépések:**

1. Csatlakoztasd a D1 Mini-t USB-n
2. Nyisd meg: [https://tasmota.github.io/install/](https://tasmota.github.io/install/)
3. Válaszd: **`tasmota.bin`** (standard ESP8266 build)
4. Kattints **Install** → válaszd ki a soros portot (Windows: COMx)
5. Engedélyezd a törlést ha tiszta telepítést akarsz
6. Várd meg a feltöltést

> Ha `tasmota.bin` nem fér el: `tasmota-lite.bin` (kisebb, kevesebb funkció)

**Hibakeresés:**
- Próbálj másik USB kábelt / portot
- Ellenőrizd a CH340/CP2102 drivert
- D3/GPIO0-t földre húzva kényszeríthető flash mód (ritkán kell)

---

## Első indítás és WiFi konfiguráció

Flash után a panel létrehoz egy AP-t:
```
Tasmota-xxxx
```
1. Csatlakozz erre WiFi-n
2. Böngészőben: `192.168.4.1`
3. Add meg a saját WiFi hálózat SSID-jét és jelszavát
4. Az eszköz csatlakozik, kap egy IP-t a routertől

**IP megtalálása:** router DHCP lista, hálózatszkenner, vagy `http://tasmota-xxxx.local`

---

## Modul beállítás

Tasmota webfelületen:  
**Configuration → Configure Module → Generic (18)**

Ezután a GPIO lábak szabadon konfigurálhatók funkcióhoz.

---

## MQTT konfiguráció

### Webfelületen
**Configuration → Configure MQTT**

| Mező | Érték |
|------|-------|
| Host | MQTT bróker IP vagy domain |
| Port | 1883 (vagy 8883 TLS-hez) |
| Client | egyedi kliensnév, pl. `D1A1B2C3` |
| User | MQTT felhasználónév (ha van) |
| Password | MQTT jelszó (ha van) |
| Topic | eszköz topic neve, pl. `A1B2C3` |
| Full Topic | `%prefix%/%topic%/` (alapértelmezett marad) |

### Konzolból (Console parancsok)

```
MqttHost    <bróker IP vagy domain>
MqttPort    1883
MqttUser    <felhasználónév>
MqttPassword <jelszó>
Topic       A1B2C3
FullTopic   %prefix%/%topic%/
Restart 1
```

Ha nincs autentikáció:
```
MqttUser 0
MqttPassword 0
```

### Ellenőrzés
Sikeres csatlakozás után a konzolon:
```
MQT: Connected
```

### Keletkező MQTT topicok (`Topic = A1B2C3`)
```
tele/A1B2C3/STATE     # eszköz állapot (WiFi, uptime)
tele/A1B2C3/SENSOR    # szenzoradatok
stat/A1B2C3/RESULT    # parancs visszajelzés
cmnd/A1B2C3/POWER     # relévezérlés fogadása
```

---

## Mozgásérzékelő (PIR) bekötés és konfiguráció

### Bekötés (pl. D1 / GPIO5-re)

```
PIR VCC  →  3V3 (vagy 5V, ha az érzékelő azt kér)
PIR GND  →  GND
PIR OUT  →  D1 / GPIO5
```

> Ha a PIR 5 V-os kimenetet ad, jelszintillesztés kell:
> ```
> PIR OUT -- 10kΩ --+-- D1 / GPIO5
>                   |
>                  20kΩ
>                   |
>                  GND
> ```
> Ez kb. 3,3 V-ra osztja az 5 V-os jelet.

### Tasmota GPIO beállítás

**Configuration → Configure Module:**
```
GPIO5 → Switch1
```
Mentés → újraindulás.

### Console beállítások

```
SwitchMode1 1     # normál kapcsoló mód
SetOption114 1    # leválasztja a Switch-et a relévezérléstől
                  # (csak MQTT eseményt küld, nem kapcsol relét)
Restart 1
```

Ha fordítva működik (mozgás nélkül aktív):
```
SwitchMode1 2
```

### Keletkező MQTT üzenetek

Mozgás észlelve:
```json
stat/A1B2C3/RESULT  →  {"Switch1":"ON"}
```
Mozgás megszűnt:
```json
stat/A1B2C3/RESULT  →  {"Switch1":"OFF"}
```

---

## Parancsküldés a szerverről

```
Topic:   cmnd/A1B2C3/POWER
Payload: ON
```

```
Topic:   cmnd/A1B2C3/POWER
Payload: OFF
```

---

## Projekt státusz

- [x] Tasmota telepítési leírás elkészült (Viktor → Sogi)
- [x] Teszt szerver kész: Bálint beállította, email értesítés megy, ha az eszköz üzenetet küld
- [ ] Sogi megkapja a szerver MQTT beállításokat (Bálinttól)
- [ ] D1 Mini csatlakoztatva a teszt szerverhez
- [ ] PIR szenzor teszt
