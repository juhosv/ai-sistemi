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

### Router beállítás – Tasmota / ESP32 kompatibilitás

> **Tapasztalat (2026-06-21):** A Tasmota eszközök **2,4 GHz-es WiFi-n** kommunikálnak (IEEE 802.11 b/g/n). **Nem szeretik**, ha a router úgy van beállítva, hogy **egy SSID név alatt** egyszerre elérhető a **2,4 GHz és a 5 GHz** is (band steering / „smart connect"). Ilyen hálózaton az eszközök gyakran instabilak, nem csatlakoznak, vagy időnként leesnek.

Ha ilyen routerrel találkozunk a helyszínen, **érdemes külön hálózatot** létrehozni az IoT eszközöknek. Két lehetséges megoldás:

| Megoldás | Leírás |
|----------|--------|
| **Guest WiFi** | Külön vendég hálózat **külön SSID névvel** – ha a router támogatja, csak 2,4 GHz-re korlátozva |
| **Második SSID** | Ha a router támogatja a külön WiFi hálózat létrehozását, dedikált SSID az eszközöknek |

#### Ajánlott beállítások (dedikált IoT SSID)

| Beállítás | Érték | Megjegyzés |
|-----------|-------|------------|
| **Sáv** | Csak **2,4 GHz** | Az ESP32/ESP8266 nem tud 5 GHz-re csatlakozni |
| **Biztonság** | **WPA2-Personal** | Tasmota-kompatibilis |
| **WPA3** | **Kikapcsolva** ennél a hálózatnál | WPA3-only hálózaton sok IoT eszköz nem működik |
| **Csatornaszélesség** | **20 MHz** | 40 MHz széles csatorna instabilitást okozhat IoT-nál |
| **SSID elrejtése** | **Nem** (hidden SSID off) | Rejtett SSID nehezíti a csatlakozást és újracsatlakozást |
| **Jelszó** | **Külön jelszó** | Ne ugyanaz legyen, mint a fő hálózat jelszava |

#### Telepítési gyakorlat

1. Helyszíni WiFi szkennelés (Tasmota Manager `WifiScan`, vagy eszköz AP mód) – melyik SSID látszik, milyen jelerősséggel
2. Ha csak egy kombinált SSID van → kérjük az ügyfelet / IT-t a fenti dedikált 2,4 GHz hálózat létrehozására
3. Tasmota **SSID1** = dedikált IoT hálózat; **SSID2** = opcionális tartalék (pl. mobil hotspot). ESPHome flottánál: [`wifi.networks` + `priority`](#esphome--több-wi-fi-hálózat-elsődleges--másodlagos)
4. Dokumentálni: SSID név, jelszó, router típus, ki állította be

→ Tasmota Manager WiFi szkennelés: [`user-guide/README.md`](user-guide/README.md) – Config / WiFi fejezet

#### Saját router az ügyfélnek (több projekt esetén)

> **Ötlet (2026-06-21):** Ha **több projekt** készül (több helyszín, több ügyfél), érdemes elgondolkodni azon, hogy **mi adjunk az ügyfélnek egy routert**, amely **előre úgy van beállítva**, hogy a SmartBlue / Tasmota eszközöknek megfelelő legyen.

**Miért érdemes?**

| Probléma ma | Saját routerrel |
|-------------|-----------------|
| Ügyfél routere band steeringgel (2,4+5 GHz egy SSID) | Előre konfigurált, csak 2,4 GHz IoT SSID |
| IT nem enged új SSID-t / nem ért hozzá | Mi telepítjük, mi ismerjük a beállításokat |
| Minden helyszín más WiFi környezet | Egységes, ismert konfiguráció minden pilotnál |
| Telepítési idő: router beállítás helyszínen | Plug-and-play – csak bedugni, eszközök már jó SSID-re vannak konfigurálva |

**Milyen router kell?**

- **Viszonylag olcsó** modell is elég – a lényeg, hogy **megbízhatóan tudja a 2,4 GHz-et** (külön SSID vagy legalább külön 2,4 GHz hálózat)
- Nem kell drága mesh / WiFi 6 – IoT eszközök alacsony sávszélességet igényelnek
- Előnyös, ha: külön SSID létrehozható, WPA2, 20 MHz csatorna, nincs kényszerített WPA3

**Telepítési modell (tervezett)**

```
[Ügyfél meglévő internet] ──► WAN ──► [SmartBlue IoT router]
                                              │
                                              │ 2,4 GHz WiFi
                                              │ SSID: SmartBlue-IoT-XXXX
                                              ▼
                                        [ESP32 eszközök]
```

- A router **WAN porton** csatlakozik az ügyfél hálózatához (internet + opcionálisan elérés a szerver felé)
- Az eszközök **csak a mi IoT WiFi-nkre** kapcsolódnak – elkülönülnek az ügyfél fő hálózatától
- SSID/jelszó **projektenként** vagy **ügyfelenként** egyedi lehet (pl. utolsó 4 karakter a helyszín kódjából)

**Gyártás / előkészítés (Zsolti / telepítő):**

1. Router kiválasztása, beszerzés (tömeges, egységes típus)
2. Előre beállítás: 2,4 GHz SSID, WPA2, 20 MHz, WPA3 off, DHCP
3. SSID + jelszó dokumentálása → Tasmota eszközök SSID1 mezője már ezt kapja (Tasmota Manager profil)
4. Helyszínen: bedugás, WAN bekötés, teszt

**Nyitott kérdések**

- [ ] Konkrét router modell / ár (Hestore, TP-Link, stb.)?
- [ ] Hány db készleten tartani?
- [ ] Az ügyfélnek marad a router, vagy kölcsön / bérleti modell?
- [ ] Szerbiai tápellátás / csatlakozó (EU plug)?
- [ ] VLAN / elkülönítés szükséges-e az ügyfél IT-től?

→ Beszerzési jelöltek: [`beszerzes.md`](beszerzes.md)

### ESPHome – több Wi-Fi hálózat (elsődleges / másodlagos)

Az **ESPHome** teljes mértékben támogatja az elsődleges, másodlagos és további Wi-Fi hálózatokat – nem egyetlen SSID-hez vagyunk kötve. A Tasmota **SSID1 / SSID2** megfelelője ESPHome-ban a `wifi.networks` lista.

→ ESPHome flotta kontextus: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md#beüzemelés-helyszínen)

#### 1. Prioritás alapú (elsődleges / másodlagos)

A `priority` mezővel sorrendezhető a hálózatok. Indításkor a **legmagasabb prioritású** hálózathoz csatlakozik; ha az elérhetetlen, **automatikusan** a következőre vált.

```yaml
wifi:
  networks:
    - ssid: "Elsodleges_Ceges_WiFi"
      password: !secret wifi_primary
      priority: 100

    - ssid: "Masodlagos_Tartalek_WiFi"
      password: !secret wifi_backup
      priority: 50

    - ssid: "Szerelo_Mobil_Hotspot"
      password: !secret wifi_hotspot
      priority: 10

captive_portal:
```

| Prioritás | Tipikus szerep |
|-----------|----------------|
| 100 | Elsődleges – ügyfél / IoT dedikált Wi-Fi |
| 50 | Másodlagos – tartalék router, extender SSID |
| 10 | Végső tartalék – szerelő mobil hotspot |

**SmartBlue pre-staging (műhely):** irodai Wi-Fi magas prioritással → helyszíni SSID alacsonyabbal; műhelyben teszt, helyszínen automatikus váltás.

#### 2. Jelerősség alapú (RSSI)

Ha **nincs** `priority` megadva, indításkor az ESPHome **szkennel**, és a **legjobb RSSI**-jű hálózathoz csatlakozik (pl. földszint vs. emeleti extender):

```yaml
wifi:
  networks:
    - ssid: "Haz_Foldszint_WiFi"
      password: !secret wifi_pass
    - ssid: "Haz_Emelet_Extender"
      password: !secret wifi_pass

captive_portal:
```

#### 3. Captive Portal biztonsági háló

A több hálózat és a Captive Portal **együtt** működik:

```
Indítás → próbálja a networks listát (prioritás vagy RSSI szerint)
       → ha mind sikertelen → Captive Portal AP
       → szerelő új SSID + jelszó → mentés a listához
```

| Eset | Viselkedés |
|------|------------|
| Áramszünet – router lassabban indul | ESP újrapróbálja a listát, majd AP mód |
| Megváltozott Wi-Fi jelszó | Csatlakozás sikertelen → Captive Portal |
| Elsődleges router leáll | Automatikus váltás másodlagosra (ha elérhető) |

Ez növeli a **rendelkezésre állást** – triakos ventilátor, szenzorok stabilabb üzemelése ügyfélnél.

#### ESPHome vs Tasmota – Wi-Fi tartalék

| | Tasmota | ESPHome |
|---|---------|---------|
| Elsődleges | SSID1 | `networks[0]` vagy legmagasabb `priority` |
| Másodlagos | SSID2 | További `networks` elemek |
| Harmadik+ | Korlátozott | ✓ Tetszőleges számú hálózat a listában |
| Helyszíni új Wi-Fi | AP mód / WebUI | **Captive Portal** |

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

### ESPHome és GSM – fontos korlát (2026-06-23)

Az ESPHome architektúráját (és a Native API-t) **folyamatos, nagy sávszélességű helyi hálózatra** (Wi-Fi, Ethernet) tervezték. A GSM/LTE mint **elsődleges internetkapcsolat** az ESPHome gyári komponenseivel **nem támogatott**.

→ Részletes firmware szempontok: [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md#gsm-kommunikáció--esphome-korlátok)

#### Mit tud az ESPHome natívan?

| Funkció | Támogatás | Példa modul |
|---------|-----------|-------------|
| SMS küldés/fogadás | ✓ | SIM800L |
| Hívás észlelés (Caller ID) | ✓ | SIM800L |
| USSD lekérdezés | ✓ | SIM800L |
| **GPRS/4G adatforgalom (MQTT/IP)** | **✗ gyári komponens nincs** | – |

Az ESPHome **nem használja a GSM modult IP gateway-ként** – a beépített MQTT kliens így **nem tud mobilneten** csatlakozni a ThingsBoard szerverhez.

**SMS-re alkalmas:** riasztás áramszünetkor, SMS paranccsal relé kapcsolás – ezekhez az ESPHome SIM800L komponense megfelelő.

#### GSM adatkapcsolat ThingsBoard-hoz – három út

| # | Megoldás | Firmware | Előny | Hátrány |
|---|----------|----------|-------|---------|
| **1** | **Arduino/C++ + TinyGSM** | Egyedi (nem ESPHome) | Natív 4G/LTE (SIM7600, A7670); tiszta MQTT JSON → ThingsBoard | Nincs YAML, nincs Captive Portal |
| **2** | **Külső 4G Wi-Fi router** | **ESPHome** (változatlan) | Megmarad Captive Portal, OTA, sablon flotta; ESP Wi-Fi-n csatlakozik a routerre | Extra hardver + SIM a routerben |
| **3** | **ESPHome custom_component** | ESPHome + C++ | Elméletileg összekapcsolható | Komoly fejlesztés; elveszik a kódmentes egyszerűség |

**1. megoldás részletei:** pl. LilyGO T-Call ESP32 (gyári SIM foglalat) + [TinyGSM](https://github.com/vshymanskyy/TinyGSM) – APN beállítás, MQTT kliens, ugyanaz a ThingsBoard üzenetformátum, mint Wi-Fi-s ESPHome eszközöknél.

**2. megoldás (javasolt, ha ESPHome marad):** ipari vagy olcsó USB 4G modem/router a helyszíni dobozban; az ESP továbbra is a meglévő Wi-Fi sablonnal működik.

**SmartBlue stratégia (előzetes):**
- **1. fázis / pilot:** Wi-Fi (beltéri, garantált lefedettség) – ESPHome
- **2. fázis / terepi:** GSM helyszíneken **4G router + ESPHome** vagy **TinyGSM egyedi firmware** – döntés helyszínenként
- **SMS riasztás:** ESPHome SIM800L komponens kiegészítésként (nem adatcsatorna)

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

### LoRa – nem Wi-Fi repeater

Ha a Wi-Fi hatótáv **több száz méter – kilométer** kell, a **LoRa** alternatíva – de **nem hosszabbítja a Wi-Fi jelet**. Különálló rádiócsatorna (EU: **868 MHz**), más fizika:

| | Wi-Fi | LoRa |
|---|-------|------|
| Tipikus hatótáv (falak között) | 20–50 m | 100–500 m (épületben); **1–5 km** szabad területen |
| Áthaladás | Gyenge fém/vastag falnál | Jobb – szub-GHz |
| Szerep | Internet / MQTT közvetlenül | Csak **helyi rádió** → gateway → MQTT |

→ Részletes ESPHome + ThingsBoard felépítés: [LoRa szekció](#4-lora-kommunikáció), [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md#lora--hatótáv-növelés-esphome--thingsboard)

---

## 4. LoRa kommunikáció

### Mi az a LoRa?

A **LoRa** (Long Range) rádió moduláció, amelyet az IoT eszközök számára fejleszttek ki. Az LPWAN (Low Power Wide Area Network) kategóriába tartozik. Fő tulajdonságai:

- **Hatótávolság:** szabad területen 1–5 km (line-of-sight akár 5–15 km), városban 1–3 km; épületen belül 100–500 m
- **Wi-Fi-hez képest:** **nem repeater** – külön 868 MHz-es rádió; Wi-Fi falak között gyakran 20–50 m, LoRa km-es távolságot is áthidal
- **Áramfogyasztás:** rendkívül alacsony (sleep módban µA szint)
- **Sávszélesség:** nagyon alacsony (250 bps – 50 kbps) – csak kis adatcsomagok
- **Frekvencia:** Európában 868 MHz (licence-mentes ISM sáv)
- **Protokoll:** LoRa (fizikai réteg); felette **ESPHome Packet Transport** (pont-pont) vagy **LoRaWAN** (hálózati réteg)

### ESPHome + ThingsBoard: Gateway–Node architektúra (2026-06-23)

A LoRa modulok **nem kapnak IP-címet** – nem csatlakoznak közvetlenül MQTT brókerhez. **Mester–szolga (Gateway–Node)** felépítés:

```
Távoli szenzor (Node)              Központi átjáró (Gateway)           Szerver
ESP32 + LoRa (SX1262/1276)         ESP32 + LoRa + Wi-Fi                 ThingsBoard CE
     │ méri: hő, PWM stb.                │                                  │
     │ LoRa rádió (868 MHz)              │                                  │
     └──────── adatcsomag ──────────────►│ fogad                            │
                                         │ Wi-Fi / Ethernet                 │
                                         └──────── MQTT ───────────────────►│
```

| Szerep | Hol | Firmware |
|--------|-----|----------|
| **Node** | Mező, pince, kert vége, fémkonténer | ESPHome – mér, **1–5 percenként** küld rövid csomagot |
| **Gateway** | Főépület – ahol van Wi-Fi | ESPHome – LoRa fogad, **MQTT** továbbít TB-re |

**ESPHome natív támogatás:** SX126x / SX127x chip komponensek + **Packet Transport** platform – két ESPHome eszköz LoRa-n beszélget, szenzorértékek automatikusan átmennek az átjáróra, C++ kód nélkül.

→ [`firmware-esphome-dontes.md`](firmware-esphome-dontes.md#lora--hatótáv-növelés-esphome--thingsboard)

### Mikor érdemes LoRa-t használni

| Szituáció | WiFi | GSM | LoRa |
|-----------|------|-----|------|
| Épületen belül, WiFi van, de távoli pont (200+ m) | ⚠️ repeater | – | **✅** |
| Épületen belül, nincs WiFi | – | ✅ | ⚠️ gyenge |
| Terepi, van mobilnet | – | ✅ | – |
| Terepi, **nincs mobilnet** | – | – | ✅ |
| Nagy terület, saját hálózat | – | – | ✅ |
| Akkumulátoros, ritkán küld | ✅ | ⚠️ | ✅ |

**SmartBlue felhasználási esetek:**
- Terepi helyszín, nincs megbízható GSM – saját LoRa gateway a főépületben
- **Egy telephely:** Wi-Fi a főépületben, szenzor 200 m-re (kert, konténer, szomszéd épület) – LoRa node + egy gateway
- Mezőgazdasági terület – több node, egy-két gateway

### ESP32 + LoRa hardver lehetőségek

| Modul / Board | Leírás | Megjegyzés |
|---------------|--------|------------|
| **Heltec WiFi LoRa 32 (V3)** | ESP32-S3 + SX1262 + OLED | Legelterjedtebb; Wi-Fi **és** LoRa egy lapon – gateway vagy node |
| **LilyGO T-Beam / T-Echo** | ESP32 + LoRa + opcionális GPS | Terepi, akkumulátoros node-hoz |
| **TTGO LoRa32** | ESP32 + SX1276/SX1278 + OLED | Olcsó, elterjedt |
| **RAK4631 (WisBlock)** | nRF52840 + SX1262 | Prémium, de nem ESP32 |
| **ESP32 + SX1276 breakout** | SPI összekötés | Egyedi NYÁK-hoz |

> **Heltec WiFi LoRa 32:** ideális **gateway** – Wi-Fi + LoRa egy boardon. Távoli **node** lehet egyszerűbb LoRa-only board (alacsonyabb fogyasztás).

### Két út a szerverig

#### A) ESPHome Packet Transport (javasolt SmartBlue + ThingsBoard-hoz)

```
Node (ESPHome) ──LoRa──► Gateway (ESPHome) ──MQTT──► ThingsBoard CE
```

- Nincs külön LoRaWAN Network Server
- Ugyanaz a toolchain, mint Wi-Fi-s flottánál
- Gateway ESPHome YAML + MQTT konfig

#### B) LoRaWAN infrastruktúra (alternatíva)

LoRaWAN hálózathoz külön network server kell:

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
ThingsBoard CE (MQTT)
```

> **Megjegyzés:** A korábbi diagram FastAPI backendre hivatkozott – ThingsBoard irányban a gateway MQTT végpontja a TB.

**Opciók a Network Serverre (csak LoRaWAN útnál):**

| Opció | Leírás | Költség |
|-------|--------|---------|
| **The Things Network (TTN)** | Ingyenes, publikus közösségi hálózat, globális gateway térkép | Ingyenes (korlátozott üzenetszám) |
| **ChirpStack** | Önhoszolt, nyílt forráskódú LoRaWAN Network Server | Ingyenes (saját szerver kell) |
| **Helium Network** | Decentralizált, kripto alapú | Bizonytalan jövő |

**Gateway igény:**
- Ha TTN gateway van a közelben (ttnmapper.org), gateway vásárlás nem kell
- Saját gateway: RAK7268 (~150 €), RAK7289 outdoor (~250 €)
- Indoor gateway: RAK7243 vagy Dragino LPS8 (~100 €)

### Korlátok és kompromisszumok

| Korlát | Következmény | SmartBlue |
|--------|--------------|-----------|
| **Alacsony sávszélesség** | Csak apró csomagok: `MAC, Temp: 24.5, PWM: 0.8` | Elég szenzoradathoz |
| **Nincs FOTA LoRa-n** | ESPHome `.bin` frissítés **nem** megy át LoRa-n | Node OTA: **Wi-Fi közelben** vagy gateway-n keresztül kábelesen |
| **Duty cycle (868 MHz)** | Max. ~**1%** adásidő – óránként ~36 mp | Küldés **1–5 percenként**, nem másodpercenként |
| **Késleltetett parancsok** | TB csúszka / Shared Attribute **nem azonnali** | Node felébred → küld → gateway visszaküldhet beállítást – **percek** |
| **LoRaWAN vs Packet Transport** | LoRaWAN: extra network server | ESPHome Packet Transport: **egyszerűbb** TB integráció |

- Valós idejű vezérlés (PWM csúszka azonnal): **Wi-Fi vagy GSM** jobb; LoRa-ra ritkított paraméterezés
- Korábbi Tasmota `cmnd/stat/tele` LoRaWAN-ra nem natív – ESPHome Packet Transport + MQTT gateway megoldja

### Összefoglalás – mikor érdemes vizsgálni a LoRa-t

A SmartBlue projekt **jelenlegi fázisában (beltéri, WiFi garantált)** a LoRa nem szükséges. Akkor lesz releváns, ha:

- Terepi telepítések jönnek, ahol nincs GSM lefedettség
- Nagy területen (gyár, farm) sok eszközt kell lefedni alacsony költséggel
- Akkumulátoros eszközökhöz ultra-alacsony fogyasztás kell
- Saját privát LoRa gateway (1 gateway → sok node) – **ESPHome Packet Transport** vagy LoRaWAN
- Wi-Fi van a főépületben, de a szenzor **200+ m-re** – LoRa node + gateway

### Nyitott kérdések LoRa kapcsán

- [ ] Van-e a pilot helyszíneken olyan terület, ahol WiFi / GSM nem megbízható?
- [ ] Robi / Alfréd riasztós / kamerás munkáinál előfordul-e ilyen helyszín?
- [ ] **ESPHome Packet Transport pilot** – Heltec gateway + egy távoli node
- [ ] Packet Transport vs LoRaWAN – melyik út a hosszú távú standard?
- [ ] ChirpStack / TTN – csak ha LoRaWAN irány

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
