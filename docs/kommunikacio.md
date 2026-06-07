# Kommunikációs lehetőségek – WiFi, GSM 4G, LoRa, külső antenna

## Összefoglaló

Az ESP32-alapú eszközcsaládban két kommunikációs módot vizsgálunk. Mindkettőnek van beépített ESP32 támogatása (WiFi natív, GSM külső modul), és a szerver protokoll réteg mindkét esetben azonos lehet (MQTT, HTTP/HTTPS).

---

## 1. WiFi kommunikáció

### Előnyök
- Az ESP32 **natívan támogatja** (külső modul nem szükséges)
- **Alacsony fogyasztás** – különösen deep sleep + WiFi wake-up kombinációval
- **Gyors adatátvitel**, nagy sávszélesség
- **Olcsóbb hardver** (nincs GSM modul)
- Egyszerűbb OTA frissítés és konfiguráció letöltés

### Hátrányok
- **Helyi hálózat szükséges** – terepi telepítésnél problémás lehet
- **Hatótávolság korlátozott** – router közelség szükséges
- WiFi hálózat adminisztrációja az ügyfélnél (SSID, jelszó, tűzfal)
- Megbízhatatlan hotspot esetén kapcsolat-kiesések

### Tipikus alkalmazási területek
- Épületen belüli telepítések
- Gyárban, raktárban, ahol van WiFi infrastruktúra
- Olyan helyszínek, ahol az ügyfél garantálja a WiFi lefedettséget

---

## 2. GSM 4G kommunikáció

### Lehetséges modulok ESP32 mellé

| Modul | Szabvány | Megjegyzés |
|-------|----------|------------|
| SIM7600 | LTE Cat-4 (full 4G) | Nagy sebesség, drágább |
| SIM7070G | LTE Cat-M + NB-IoT + GPRS | IoT-optimált, alacsony fogyasztás |
| A7680C | LTE Cat-1 | Közép-kategória, jó ár/érték arány |
| SIM800L | 2G GPRS | Olcsó, de 2G kivezetés miatt kockázatos |

> **Szerbia esetén:** Ellenőrizni kell, hogy a helyi operátorok (Telekom Srbija, A1, Yettel) milyen LTE Cat-M / NB-IoT lefedettséget biztosítanak. Ha nem megfelelő, LTE Cat-1 vagy Cat-4 modul javasolt.

### Előnyök
- **Hálózat-független** – SIM kártya elegendő, nincs szükség ügyfél infrastruktúrára
- **Terepi telepítésekhez ideális** – mezőgazdaság, infrastruktúra monitoring, külső objektumok
- Roaming lehetőség (EU-n belül egységes díjak)
- Könnyen skálázható nagy területen

### Hátrányok
- **Drágább hardver** (GSM modul + antenna + SIM)
- **SIM kártya és adatcsomag költség** (havidíj)
- **Magasabb áramfogyasztás** – akkumulátoros eszközöknél tervezni kell
- Lefedettségi fehér foltok terepi területeken
- Modul és ESP32 közötti kommunikáció (UART/AT parancsok) extra fejlesztési komplexitás

---

## 3. WiFi hatótávolság növelés – külső antenna

### Mikor releváns

Ha a helyszínen van WiFi, de az eszköz telepítési pontja (pl. gépterem sarka, fém szekrény, vastag fal mögötti tér) gyenge jelerőséggel rendelkezik.

### Megoldások

| Módszer | Leírás | Költség | Fejlesztési igény |
|---------|--------|---------|-------------------|
| **ESP32 U.FL / IPEX csatlakozós változat** | Az ESP32-WROOM-32U (vagy ESP32-S3-WROOM-1U) rendelkezik külső antenna csatlakozóval. U.FL kábel + dipole antenna feltéve 3–5 dBi nyereséget ad | Alacsony (~2-5 €) | Csak hardver váltás |
| **ESP32-WROVER (PCB antenna)** | Jobb mint az ESP32-WROOM belső antennája, de nem cserélhető | Nincs extra | Nincs |
| **WiFi range extender / repeater** | Olcsó WiFi repeater az eszköz közelébe telepítve | Alacsony (~10-15 €) | Semmi (hálózati megoldás) |
| **Mesh WiFi (pl. TP-Link Deco)** | Az ügyfél meglévő vagy új mesh hálózatán az eszköz lefedett | Közepes (ügyfél beruh.) | Semmi |

### Praktikus tanács

Az ESP32 modulok közül az **ESP32-WROOM-32U** vagy **ESP32-S3-WROOM-1U** változat választásával azonos kódbázis mellé cserélhető az antenna – ez minimális ráfordítással megoldja a gyenge jel problémájának nagy részét.

---

## 4. LoRa kommunikáció

### Mi az a LoRa?

A **LoRa** (Long Range) rádió moduláció, amelyet az IoT eszközök számára fejleszttek ki. Az LPWAN (Low Power Wide Area Network) kategóriába tartozik. Fő tulajdonságai:

- **Hatótávolság:** szabad területen 5–15 km, városban 1–3 km (épületen belül 100–500 m)
- **Áramfogyasztás:** rendkívül alacsony (sleep módban µA szint)
- **Sávszélesség:** nagyon alacsony (250 bps – 50 kbps) – csak kis adatcsomagok
- **Frekvencia:** Európában 868 MHz (licence-mentes ISM sáv)
- **Protokoll:** LoRa (fizikai réteg) + **LoRaWAN** (hálózati protokoll, szerver oldal)

### Mikor érdemes LoRa-t használni

| Szituáció | WiFi | GSM | LoRa |
|-----------|------|-----|------|
| Épületen belül, WiFi van | ✅ | – | – |
| Épületen belül, nincs WiFi | – | ✅ | ⚠️ gyenge |
| Terepi, van mobilnet | – | ✅ | – |
| Terepi, **nincs mobilnet** | – | – | ✅ |
| Nagy terület, saját hálózat | – | – | ✅ |
| Akkumulátoros, ritkán küld | ✅ | ⚠️ | ✅ |

**A LoRa legjobb felhasználási esete a SmartBlue projektben:** olyan terepi helyszínek, ahol sem WiFi, sem mobilnet nincs megbízhatóan, de saját LoRa gateway telepíthető (pl. egy gyártelep, raktárcsarnok, mezőgazdasági terület).

### ESP32 + LoRa hardver lehetőségek

| Modul / Board | Leírás | Megjegyzés |
|---------------|--------|------------|
| **Heltec WiFi LoRa 32 (V3)** | ESP32-S3 + SX1262 LoRa + OLED kijelző, egységes board | Legelterjedtebb, Tasmota és Arduino támogatás |
| **TTGO LoRa32** | ESP32 + SX1276/SX1278 LoRa + OLED | Olcsó, elterjedt |
| **RAK4631 (WisBlock)** | nRF52840 + SX1262, moduláris rendszer | Prémium, de nem ESP32 |
| **ESP32 + SX1276 breakout** | Szeparált modulok összekötve SPI-n | Nagyobb rugalmasság, de több összekötés |

> A **Heltec WiFi LoRa 32** különösen érdekes: egyszerre van rajta WiFi **és** LoRa, így az eszköz WiFi-vel kommunikál ahol van jel, LoRa-val ahol nincs – egyetlen hardver, hibrid kommunikáció.

### LoRaWAN szerver infrastruktúra

LoRaWAN hálózathoz kell:

```
Eszköz (ESP32+LoRa)
    │ LoRa rádió (868 MHz)
    ▼
Gateway (LoRa → Ethernet/LTE)
    │ IP hálózat
    ▼
Network Server (The Things Network / Chirpstack / egyedi)
    │ MQTT / HTTP webhook
    ▼
SmartBlue Backend (FastAPI + MQTT)
```

**Opciók a Network Serverre:**

| Opció | Leírás | Költség |
|-------|--------|---------|
| **The Things Network (TTN)** | Ingyenes, publikus közösségi hálózat, globális gateway térkép | Ingyenes (korlátozott üzenetszám) |
| **ChirpStack** | Önhoszolt, nyílt forráskódú LoRaWAN Network Server | Ingyenes (saját szerver kell) |
| **Helium Network** | Decentralizált, kripto alapú | Bizonytalan jövő |

**Gateway igény:**
- Ha TTN gateway van a közelben (ttnmapper.org), gateway vásárlás nem kell
- Saját gateway: RAK7268 (~150 €), RAK7289 outdoor (~250 €)
- Indoor gateway: RAK7243 vagy Dragino LPS8 (~100 €)

### Korlátok – mikor nem jó a LoRa

- **Kis sávszélesség:** OTA firmware frissítés LoRa-n keresztül nem praktikus (lassú)
- **Duty cycle korlát (868 MHz):** Európában max. 1% duty cycle → 1 üzenet/perc nagy adatcsomaggal
- **Valós idejű vezérlés nehéz:** parancskiadás (cmnd/) LoRa-n lassú és korlátozott
- A SmartBlue MQTT protokoll (Tasmota) nem illeszkedik natívan LoRaWAN-ra → átalakítás szükséges

### Összefoglalás – mikor érdemes vizsgálni a LoRa-t

A SmartBlue projekt **jelenlegi fázisában (beltéri, WiFi garantált)** a LoRa nem szükséges. Akkor lesz releváns, ha:

- Terepi telepítések jönnek, ahol nincs GSM lefedettség
- Nagy területen (gyár, farm) sok eszközt kell lefedni alacsony költséggel
- Akkumulátoros eszközökhöz ultra-alacsony fogyasztás kell
- Saját privát LoRa gateway hálózat gazdaságos megoldás (pl. 1 gateway → 50+ eszköz)

### Nyitott kérdések LoRa kapcsán

- [ ] Van-e a pilot helyszíneken olyan terület, ahol WiFi / GSM nem megbízható?
- [ ] Robi / Alfréd riasztós / kamerás munkáinál előfordul-e ilyen helyszín?
- [ ] Érdemes-e a Heltec WiFi+LoRa boardot kipróbálni mint univerzális hardware platform?
- [ ] ChirpStack saját szerverre kellene-e, vagy TTN elegendő?

---

## Hibrid megközelítés

Megfontolandó, hogy az eszközcsalád **mindkét módot támogassa** – az eszköz konfiguráció alapján döntsön:
- Ha WiFi elérhető → WiFi-n kommunikál (energia-hatékony)
- Ha WiFi nem elérhető → GSM 4G-n kommunikál (fallback)

Ez növeli a hardver komplexitást, de maximális flexibilitást biztosít.

---

## Összehasonlító táblázat

| Szempont | WiFi | WiFi + külső antenna | GSM 4G | LoRa |
|---------|------|----------------------|--------|------|
| Hardverköltség | Alacsony | Alacsony (+2-5 EUR) | Közepes-magas | Közepes (gateway kell) |
| Üzemeltetési költség | Alacsony | Alacsony | Közepes (SIM díj) | Alacsony (gateway után) |
| Infrastruktúra igény | WiFi hálózat | WiFi hálózat | Mobilhálózat | LoRa gateway |
| Hatótávolság | 10–100 m | 50–300 m | Korlátlan | 1–15 km |
| Terepi alkalmazás | Korlátozott | Korlátozott | Kiváló | Kiváló |
| Áramfogyasztás | Alacsony | Alacsony | Magasabb | Minimális |
| Sávszélesség | Nagy | Nagy | Közepes | Nagyon alacsony |
| OTA frissítés | Egyszerű | Egyszerű | Lehetséges | Nem praktikus |
| Valós idejű vezérlés | Jó | Jó | Jó | Korlátozott |
| Fejlesztési bonyolultság | Alacsony | Alacsony | Közepes | Magas |

---

## Döntések – pilot fázis

- [x] **Helyszín:** Beltéri telepítések
- [x] **WiFi:** Garantált lefedettség minden pilot helyszínen
- [x] **Táplálás:** Hálózati táplálás (230V / DC adapter) – akkumulátor nem releváns
- [x] **Pilot kommunikáció:** Csak WiFi – GSM modul a következő fázisra marad
- [x] **GSM SIM (következő fázis):** 1NCE IoT SIM kártyák (egyszeri díj, globális lefedettség)
