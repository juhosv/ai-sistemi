# SmartBlue Tasmota Manager – Felhasználói kézikönyv

> **Verzió:** 2026-06-07  
> **Célközönség:** Zsolti (Sogi), Robi, Alfréd – helyszíni üzembe helyezők  
> **Frissítés:** Ha az alkalmazás változik, csak a szöveget és a képernyőképeket kell cserélni.  
> Képernyőképek kezelése: [`screenshots/HOW-TO-UPDATE.md`](screenshots/HOW-TO-UPDATE.md)

---

## Tartalom

1. [Előfeltételek](#1-előfeltételek)
2. [Elindítás](#2-elindítás)
3. [Flash tab – Firmware égetés](#3-flash-tab--firmware-égetés)
4. [Kapcsolat tab – Csatlakozás az eszközhöz](#4-kapcsolat-tab--csatlakozás-az-eszközhöz)
5. [Config tab – Eszköz konfigurálása](#5-config-tab--eszköz-konfigurálása)
6. [Board tab – Vizuális pin térkép](#6-board-tab--vizuális-pin-térkép)
7. [MQTT Monitor tab – Broker figyelés](#7-mqtt-monitor-tab--broker-figyelés)
8. [Rules tab – Automatizálási szabályok](#8-rules-tab--automatizálási-szabályok)
9. [Tipikus munkafolyamat – Új eszköz üzembe helyezése](#9-tipikus-munkafolyamat--új-eszköz-üzembe-helyezése)
10. [Hibaelhárítás](#10-hibaelhárítás)

---

## 1. Előfeltételek

### Hardver
- USB-soros adapter (CH340 vagy CP2102 chip)
- ESP32 vagy ESP8266 alapú eszköz (Wemos D1 Mini, NodeMCU, ESP32 DevKit, stb.)
- USB-A – MicroUSB vagy USB-C kábel

### Driver telepítés (Windows)
Ha az eszköz nem jelenik meg a portlistában:

| Chip | Driver letöltés |
|------|-----------------|
| **CH340** (legtöbb kínai modul) | https://www.wch-ic.com/downloads/CH341SER_EXE.html |
| **CP2102** (Silicon Labs) | https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers |

> Telepítés után **újra kell indítani** a számítógépet.

### Az alkalmazás futtatása
Kicsomagolás után nem kell telepíteni. A `SmartBlue-TasmotaManager\` mappán belül:

```
SmartBlue-TasmotaManager.exe
```

> ⚠️ Az `_internal\` mappa mindig legyen az `.exe` mellett – ezek együtt alkotják az alkalmazást.

---

## 2. Elindítás

Kattints duplán a `SmartBlue-TasmotaManager.exe`-re. Megnyílik egy terminálablak:

![Főképernyő](screenshots/00-fokepernyő.png)
*(ha a kép hiányzik: lásd [screenshots/HOW-TO-UPDATE.md](screenshots/HOW-TO-UPDATE.md))*

Az alkalmazás 6 tabból áll, billentyűkkel is váltható:

| Tab | Billentyű | Funkció |
|-----|-----------|---------|
| ⚡ Flash | F1 | Firmware letöltés és égetés |
| 🖥 Kapcsolat | F2 | Csatlakozás soros porton vagy HTTP-n |
| ⚙ Config | F3 | WiFi, MQTT, GPIO konfiguráció |
| 🔌 Board | F4 | Vizuális pin állapot térkép |
| 📡 MQTT | F5 | MQTT broker monitor |
| 📋 Rules | F6 | Tasmota automatizálási szabályok |

**Kilépés:** `Q` billentyű

---

## 3. Flash tab – Firmware égetés

> Ezt a lépést csak akkor kell elvégezni, ha az eszközön még nincs Tasmota firmware,  
> vagy frissíteni kell a verziót.

![Flash tab](screenshots/01-flash-tab.png)

### Lépések

**1. Eszköz csatlakoztatása**  
Csatlakoztasd az ESP-t USB-n. Kattints a **↺ Frissítés** gombra – a port megjelenik a listában (pl. `COM3`).

**2. Firmware kiválasztása**

| Firmware | Mikor válaszd |
|---------|---------------|
| `tasmota.bin` | ESP8266 alapú eszközök (Wemos D1 Mini, NodeMCU, Sonoff) |
| `tasmota-lite.bin` | ESP8266, ha kevés a flash memória |
| `tasmota32.bin` | ESP32 alapú eszközök |
| `tasmota32s3.bin` | ESP32-S3 alapú eszközök |

**3. Letöltés**  
Kattints a **⬇ Letöltés** gombra. Az alkalmazás letölti a legfrissebb verziót a GitHub-ról.

**4. Égetés**  
Kattints a **🔥 Égetés** gombra.

> ⚠️ Égetés közben **ne húzd ki** az eszközt!  
> Az előrehaladás a „Folyamat" ablakban látható.

**5. Sikeres égetés után**  
Az eszköz újraindul és elkezd Tasmota WiFi hotspotot sugározni (`tasmota-XXXXXX` névvel).

---

## 4. Kapcsolat tab – Csatlakozás az eszközhöz

> Az alkalmazás kétféleképpen tud csatlakozni egy eszközhöz:  
> **Soros porton** (USB kábellel) vagy **HTTP-n** (WiFi hálózaton, IP cím alapján).

![Kapcsolat tab](screenshots/02-kapcsolat-serial.png)

### 4.1 Soros port kapcsolat (USB)

1. Válaszd ki a **portot** (pl. `COM3`) a legördülő listából
2. A **baud ráta** maradjon `115200` (Tasmota alapértelmezés)
3. Kattints a **Csatlakozás** gombra
4. A log ablakban megjelennek az eszköz üzenetei – ha látod a Tasmota boot üzeneteit, sikeres a kapcsolat

**Állapotjelzők:**
- `● Csatlakozva` zölden – aktív soros kapcsolat
- `WiFi: SSID... IP: 192.168.x.x` – az eszköz WiFi állapota (ha már be van állítva)

**Gyors parancsok** (a gombok sorában):
- `Status` – eszköz összefoglaló
- `Status 5` – WiFi és IP info
- `Status 11` – GPIO állapotok
- `Restart 1` – újraindítás

**Egyedi parancs küldése:**  
Írj be bármilyen Tasmota parancsot alul a beviteli mezőbe, majd nyomj Entert vagy kattints a **↵ Küldés** gombra.

---

### 4.2 HTTP kapcsolat (WiFi hálózaton)

![HTTP kapcsolat](screenshots/02-kapcsolat-http.png)

Ha az eszköz már csatlakozik a WiFi hálózathoz és ismered az IP-címét:

1. Add meg az **IP-címet** (pl. `192.168.1.100`)
2. Ha az eszközön be van állítva web jelszó, add meg a **jelszót** is
3. Kattints a **Csatlakozás** gombra

> 💡 Az IP-cím megtalálható a router admin felületén, vagy soros porton keresztül  
> a `Status 5` parancs eredményéből.

**A log ablakban** minden HTTP-n küldött parancs válasza megjelenik, pont úgy, mint soros porton.

---

### 4.3 MQTT állapot

A Kapcsolat tab alján látható az MQTT kapcsolat állapota is. A **→ MQTT tab** gombbal átnavigálhatsz az MQTT Monitorra.

---

## 5. Config tab – Eszköz konfigurálása

> Ezen a tabon állítod be a WiFi hálózatot, az MQTT broker adatokat, a GPIO kiosztást  
> és a csoporthoz tartozást.

![Config tab – alap beállítások](screenshots/03-config-alap.png)

### 5.1 Konfiguráció letöltése az eszközről

Ha az eszköz már csatlakozik (soros vagy HTTP), kattints a **⬇ Letöltés az eszközről** gombra.  
Az alkalmazás automatikusan kitölti az összes mezőt az eszköz aktuális beállításaival.

> Ez az ajánlott kiindulópont – így nem kell mindent kézzel beírni.

---

### 5.2 WiFi beállítások

| Mező | Leírás |
|------|--------|
| SSID1 | Elsődleges WiFi hálózat neve |
| Jelszó1 | Elsődleges WiFi jelszó |
| SSID2 | Tartalék WiFi hálózat (opcionális) |
| Jelszó2 | Tartalék jelszó (opcionális) |

> ⚠️ A jelszavak nem olvashatók vissza az eszközről (Tasmota biztonsági korlát) –  
> ezeket mindig kézzel kell megadni küldéskor.

---

### 5.3 MQTT beállítások

| Mező | Leírás | Példa |
|------|--------|-------|
| Host | MQTT broker IP-je vagy domain neve | `192.168.1.10` vagy `broker.emqx.io` |
| Port | MQTT port | `1883` (alap) |
| User | Broker felhasználónév (ha szükséges) | `smartblue` |
| Jelszó | Broker jelszó (ha szükséges) | – |
| Eszköz azonosító | Az eszköz egyedi neve (topic) | `A1B2C3` vagy `ventilator_1` |
| FullTopic | Topic struktúra | `%prefix%/%topic%/` |

**Csoport (User / Régió):**  
Ha a SmartBlue csoportrendszert használod, válaszd ki a felhasználót és a régiót.  
A FullTopic automatikusan frissül: `{user_id}/{regio_id}/%topic%/%prefix%/`

---

### 5.4 GPIO kiosztás

![GPIO diagram](screenshots/03-config-gpio.png)

1. Válaszd ki a **Modul / Board** típusát (pl. `Wemos D1 Mini`, `ESP32 DevKit V1`)
2. A board rajza megjelenik a pin-ekkel
3. **Kattints egy GPIO pinre** → megjelenik a jobb oldali „Pin beállítás" panel
4. Válaszd ki a **funkciót**:

| Funkció | Mire való | MQTT esemény |
|---------|-----------|-------------|
| Nyomógomb | Fizikai gomb (bemeneti impulzus) | `{"Button1":{"Action":"SINGLE"}}` |
| Kapcsoló bemenet | Be/Ki állapot érzékelő | `{"Switch1":"ON"}` |
| Relé kimenet | Kapcsolóvezérlés (kimeneti) | `cmnd/.../POWER1 ON` |
| DHT22 hőmérséklet+pára | AM2301 szenzor | `{"AM2301":{"Temperature":23.4}}` |
| DS18B20 hőmérséklet | 1-Wire szenzor | `{"DS18B20":{"Temperature":23.4}}` |
| PIR mozgásérzékelő | Mozgásvezérelt esemény | `{"Switch1":"ON"}` |
| LED | Állapotjelző LED | – |
| I2C SDA / SCL | I2C busz adatvezeték / órajel | – |
| PWM kimenet | Dimmelhető vagy fordulatszám-szabályozós | – |

> 💡 Az ismert eszközöknél (pl. Sonoff 4CH) az alkalmazás automatikusan feltölti az alapértelmezett GPIO kiosztást.

---

### 5.5 Konfiguráció küldése

Kattints a **📡 Küldés** gombra. Az alkalmazás elküldi az összes beállítást az eszközre.

> Az eszköz a konfiguráció után **automatikusan újraindul** és csatlakozik a megadott WiFi hálózathoz és MQTT brokerhez.

---

### 5.6 Profil mentése / betöltése

- **💾 Profil mentése** – elmenti az aktuális beállításokat egy `.json` fájlba a `profiles\` mappában
- **📂 Betöltés** – visszatölt egy korábban mentett profilt

> Profilokkal gyorsan konfigurálhatsz több azonos típusú eszközt.

---

### 5.7 Config backup / restore (.dmp fájl)

- **Backup letöltése** – letölti az eszköz teljes konfigurációját bináris `.dmp` formátumban
- **Restore** – visszatölt egy `.dmp` fájlt az eszközre

> A `.dmp` fájl az összes Tasmota beállítást tartalmazza – ideális biztonsági mentésnek.

---

## 6. Board tab – Vizuális pin térkép

> Élő, vizuális megjelenítés az eszköz GPIO állapotáról.

![Board tab](screenshots/05-board-monitor.png)

### Adatforrás kiválasztása

- **MQTT mód** – automatikusan frissül, ha az eszköz MQTT üzeneteket küld
- **Soros mód** – 10 másodpercenként lekéri az állapotot

### A diagram jelölései

| Jelzés | Jelentés |
|--------|---------|
| `■` zölden | Aktív / HIGH állapot (pl. relé bekapcsolva) |
| `□` halványan | Inaktív / LOW állapot |
| `⚠` ikon | Boot-érzékeny láb (óvatosan!) |
| Sárga pont | ADC only bemenet |
| Cyan pont | UART pin |

### ↺ Lekérés gomb

Kattintásra az alkalmazás lekéri az eszköz aktuális állapotát (GPIO kiosztás + Mem1 board típus).  
Ha az eszköz Mem1-ben tárol board típust, a megfelelő diagram automatikusan betöltődik.

### Relé vezérlés

Ha egy pin relé kimenetként van konfigurálva, a diagramon megjelenik egy **BE / KI** gomb – ezzel közvetlenül tudod kapcsolni a reléket.

---

## 7. MQTT Monitor tab – Broker figyelés

> Valós idejű megfigyelés: látható, hogy az eszköz milyen üzeneteket küld a brokernek.

![MQTT Monitor](screenshots/04-mqtt-monitor.png)

### Csatlakozás

1. Add meg a **Host** és **Port** értékeket (ugyanazok, mint a Config tabban)
2. A **Topic szűrő** alapértelmezetten `#` (minden üzenet) – szűkíthető pl. `A1B2C3/#`-ra
3. Kattints a **Csatlakozás** gombra

### A három panel

**Bal panel – Topic fa:**  
Az összes eszköz hierarchikusan rendezve. Amelyik az utóbbi 60 másodpercben küldött üzenetet, `● Online` jelzést kap.

**Jobb panel – Payload nézet:**  
Kattints egy topicra a bal panelen → jobb oldalon megjelenik az utolsó üzenet tartalma (JSON formázva).

**Alsó log:**  
Görgethetős napló az összes beérkező üzenetről, időbélyeggel.

### Szűrés

- **Prefix szűrő:** csak `tele/`, `stat/` vagy `cmnd/` üzenetek
- **Eszköz szűrő:** csak egy adott eszköz topic-jainak megjelenítése

---

## 8. Rules tab – Automatizálási szabályok

> Tasmota Rules lehetővé teszi, hogy az eszköz önállóan reagáljon eseményekre  
> – szerver kapcsolat nélkül is.

![Rules tab](screenshots/06-rules.png)

### Szabály összeállítása

1. Válaszd ki a **kiváltó eseményt** (trigger): pl. `Switch1#State`, `DS18B20#Temperature`
2. Válaszd ki a **feltételt**: pl. `>`, `<`, `=`, értékkel
3. Válaszd ki a **GPIO-t** és a **műveletet**: pl. relé BE, relé KI, PWM érték
4. Kattints a **+ Hozzáadás** gombra
5. A szabályok listájában látható az összeállított Rule szintaxis

### Küldés az eszközre

A **📡 Küldés** gomb elküldi a szabályokat az eszközre és aktiválja őket.

### Példa: hőmérséklet-vezérelt relé

```
Ha DS18B20#Temperature > 35  →  POWER1 ON   (relé be)
Ha DS18B20#Temperature < 30  →  POWER1 OFF  (relé ki)
```

---

## 9. Tipikus munkafolyamat – Új eszköz üzembe helyezése

```
1. FLASH  →  Firmware égetése (csak első alkalommal vagy frissítéskor)
      ↓
2. KAPCSOLAT  →  Csatlakozás soros porton (USB kábellel)
      ↓
3. CONFIG  →  WiFi + MQTT + GPIO + Csoport beállítása → Küldés
      ↓
4. Eszköz újraindul, csatlakozik a WiFi-hez és az MQTT brokerhez
      ↓
5. BOARD  →  ↺ Lekérés → ellenőrzöd a GPIO-kat és az eszköz állapotát
      ↓
6. MQTT MONITOR  →  Megerősíted, hogy az eszköz üzeneteket küld
      ↓
7. (opcionális) RULES  →  Automatizálási szabályok beállítása
```

> 💡 Ha az eszköz már WiFi-n elérhető, a 2. lépéstől HTTP kapcsolattal is dolgozhatsz (nem kell USB kábel).

---

## 10. Hibaelhárítás

### Az eszköz nem jelenik meg a portlistában

1. Ellenőrizd a USB kábelt – néhány kábel csak töltő, nem adatátviteli
2. Telepítsd a CH340 vagy CP2102 drivert (lásd [1. fejezet](#1-előfeltételek))
3. Indítsd újra a számítógépet a driver telepítés után
4. Kattints az **↺ Frissítés** gombra a portlistán

---

### Égetés sikertelen

| Hibaüzenet | Megoldás |
|-----------|---------|
| `Failed to connect to ESP` | Tartsd lenyomva a BOOT gombot égetés közben (ESP32), vagy próbáld `74880` baudon |
| `A serial exception error occurred` | Zárd be az összes más programot, amely használja a portot (pl. Arduino IDE) |
| `esptool not found` | Telepítsd: `pip install esptool` |

---

### Nem jön létre a soros kapcsolat

- Ellenőrizd, hogy a baud ráta `115200`
- Próbáld meg újraindítani az ESP-t (RST gomb vagy áramtalan)
- Ellenőrizd, hogy nem használja más program a portot

---

### Az eszköz nem csatlakozik a WiFi-hez

1. Ellenőrizd az SSID-t és jelszót (kis/nagybetű érzékeny!)
2. Az ESP8266 csak **2.4 GHz**-es hálózathoz tud csatlakozni (nem 5 GHz)
3. Soros logon `WIF:` kezdetű sorok mutatják a WiFi csatlakozás állapotát

---

### Az MQTT üzenetek nem érkeznek

1. Ellenőrizd, hogy a broker IP és port helyes
2. Ellenőrizd az MQTT user/jelszót (ha van)
3. Az eszköz logon `MQT:` kezdetű sorok mutatják az MQTT kapcsolat állapotát
4. Az MQTT Monitor tabban csatlakozz a brokerhez és figyeld a `#` topicot

---

### A konfiguráció letöltés nem működik

- Győződj meg róla, hogy az eszköz csatlakozik (soros vagy HTTP)
- HTTP kapcsolatnál ellenőrizd az IP-t és a jelszót
- Ha a „Letöltés" gomb után nem töltődnek be az adatok, ellenőrizd a Serial log-ot a hibaüzenetekért

---

*Kézikönyv utolsó frissítése: 2026-06-07*  
*Kérdések / hibák: Viktor → projekt koordinátor*
