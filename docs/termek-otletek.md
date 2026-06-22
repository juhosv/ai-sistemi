# Termék ötletek

> Ötletek, amelyek a SmartBlue platform alapján megvalósíthatók. Nem végleges roadmap – inkább inspirációs lista és lehetséges irányok.

---

## 💡 Konnektoros „panic button" eszköz

### Koncepció

Egy konnektorba dugható kis doboz, amelyen egyetlen nyomógomb van. Megnyomáskor értesítést küld a beállított személyeknek (hozzátartozók, gondozók stb.).

> **Kibővítés (2026-06-21):** az eszközt ki kell egészíteni **emberi jelenlét érzékeléssel** (mmWave radar, pl. LD2410C). Ha az adatokat **AI-val elemezzük**, további következtetések vonhatók le – pl. megváltozott egy személy mozgásának / jelenlétének szokása.

### Célcsoport
- **Elsődleges:** Idős emberek, akik egyedül élnek
- **Másodlagos:** Betegek, gyengélkedők, gyerekek felügyelete
- **Intézményi:** Idősotthon, gondozási intézmény

### Hogyan működne

```
1. Eszköz konnektorba dugva → folyamatos táplálás, WiFi kapcsolat
2. LD2410C folyamatosan méri: van-e jelenlét a szobában (mozgó + álló ember)
3. Felhasználó megnyomja a gombot (SOS / OK)
4. ESP32 MQTT üzenetet küld a szervernek (gomb esemény + jelenlét állapot)
5. Szerver / AI agent elemzi az adatokat idősorban
6. Értesítés a hozzátartozóknak (push / SMS / email) – esemény vagy AI riasztás alapján
7. Opcionális: visszajelzés az eszközön (LED, hangjelzés)
```

### Jelenlét érzékelés + AI elemzés

A nyomógomb önmagában csak **reaktív** (a felhasználónak kell nyomnia). A **jelenlét szenzor** passzív, folyamatos adatot ad:

| Adatforrás | Mit mér | AI-ból levonható következtetés |
|------------|---------|--------------------------------|
| **LD2410C** (jelenlét) | Van/nincs ember, mozgó vs. álló, távolság zónák | Szokásos napi aktivitási minta; hirtelen változás (pl. reggel 8-ig mindig volt jelenlét, ma nincs) |
| **Nyomógomb** (SOS / OK) | Explicit check-in, segítségkérés | Összevetés: volt jelenlét, de nem nyomta meg az OK gombot |
| **Kombinált idősor** | Jelenlét + gomb események | „Megváltozott a mozgás szokása" – pl. kevesebb mozgás, hosszabb ülés, szokatlan éjszakai aktivitás |

```
LD2410C ──► jelenlét idősor ──┐
Nyomógomb ──► események ──────┼──► InfluxDB ──► AI agent (Hermes)
                              │                      │
                              │                      ▼
                              └──► szokásprofil   riasztás: „szokatlan nap"
```

Példa riasztások (AI-generált vagy szabály-alapú):
- Reggel 10 óráig nem volt jelenlét (pedig minden nap 7–8 között fel szokott kelni)
- 48 órája nincs OK check-in **és** alacsony a jelenlét aktivitás
- Éjszaka szokatlanul sok mozgás (esés, nyugtalanság gyanú)

### Hardver elemek
- ESP32 (WiFi beépített)
- 1 db nyomógomb (vagy több: SOS + OK/Megvagyok)
- **LD2410C** mmWave jelenlét érzékelő (Hi-Link) – lásd [`beszerzes.md`](beszerzes.md)
- Tápegység modul (230V AC → 3.3V/5V DC, konnektoros formátum)
- LED visszajelző
- Opcionális: kis buzzer (hangjelzés)
- Műanyag konnektoros doboz

### Lehetséges gombok / funkciók

| Gomb | Funkció |
|------|---------|
| Piros SOS | „Segítség kell" – azonnali riasztás |
| Zöld OK | „Megvagyok, minden rendben" – napi check-in |
| (automatikus) | Ha X ideig nem nyomja meg az OK gombot → riasztás |

### Értesítési logika ötletek

- **Egyszerű:** gomb megnyomás → SMS / Telegram az összes hozzátartozónak
- **Okosabb:** ha nem érkezik napi „OK" jelzés → automatikus riasztás
- **Ismétlés:** ha 5 percen belül senki nem nyugtázza → újra értesítés

### Előnyök
- Konnektorba dugható → nem kell tölteni, nem merül le
- Egyszerű használat (1 gomb) – az idős embernek nem kell semmit tanulnia
- **Passzív felügyelet** jelenlét szenzorral – nem kell mindig nyomkodni
- AI szokásprofil → korai figyelmeztetés gomb megnyomása nélkül is
- Nem kell mobiltelefon / tablet az idős embernek
- Olcsón legyártható az ESP32 platform miatt
- A SmartBlue szerver infrastruktúra azonnal használható

### Nyitott kérdések
- [ ] WiFi helyett GSM legyen-e? (WiFi: olcsóbb, de router kell; GSM: önálló, de SIM kell)
- [ ] Milyen értesítési csatorna a legfontosabb? (SMS, push, Telegram?)
- [ ] Kell-e visszajelzés az eszközön a sikeres küldésről? (LED / hang)
- [ ] Legyen-e „check-in" funkció (napi OK gomb)?
- [ ] Intézményi vagy otthoni piac az elsődleges?
- [ ] LD2410C GPIO (van/nincs) elég, vagy UART adatok (távolság, mozgó/álló) is kellenek az AI-hoz?
- [ ] Milyen időablakok / szokásprofil paraméterek legyenek az első verzióban?
- [ ] GDPR: jelenlét adat tárolása és hozzátartozói hozzáférés jogi keretei

---

## 📡 Bluetooth (BLE) alapú személy-érzékelés

> **Ötlet (2026-06-21):** ha folyamatosan monitorozzuk, hogy **milyen nevű Bluetooth eszközöket** lát az ESP32 a környezetben, abból is lehet következtetni dolgokra – pl. szokás változásokra. **A részletek még kidolgozandók.**

### Koncepció

Az ESP32 **BLE scan** módban passzívan figyeli a közeli Bluetooth Low Energy eszközöket. A felhasználó (vagy gondozó) regisztrálja, mely eszköznevek / MAC címek „tartoznak" az adott személyhez (pl. telefon, okosóra, fülhallgató).

```
ESP32 BLE scan ──► látható eszközök listája (név, MAC, RSSI, időbélyeg)
                         │
                         ▼
                   SmartBlue szerver ──► AI agent
                         │
                         ▼
              „Ma 9 óráig nem láttuk János telefonját"
              „Szokatlan új eszköz jelent meg este 23-kor"
```

### Mit lehet következtetni?

| Megfigyelés | Lehetséges következtetés |
|-------------|--------------------------|
| Szokásos eszköz reggel megjelenik | A személy felkelt / otthon van |
| Szokásos eszköz nem jelenik meg X órán át | Eltérés a napi rutintól – riasztás |
| Eszköz RSSI hirtelen eltűnik | Elment otthonról (telefon magával) |
| Új, nem regisztrált eszköz | Látogató? – kontextustól függ |
| Éjszakai eszköz-mintázat változás | AI: szokás változás, érdemes figyelni |

### Kapcsolat más ötletekkel

- **Panic button + jelenlét:** BLE és LD2410C **kiegészítik** egymást – BLE a személy telefonját „látja", a radar a fizikai jelenlétet méri gomb nélkül
- **AI agent:** ugyanaz a Hermes / idősor elemzés pipeline – BLE scan eredmények is InfluxDB-be kerülnek
- **Provisioning fejezet BLE-je más cél:** ott BLE a *WiFi beállításhoz* kell; itt BLE az *érzékelés*

### Technikai kiinduló pontok (TBD)

- ESP32 natív BLE scan (Bluedroid / NimBLE) – Tasmota támogatás ellenőrizendő, esetleg custom firmware
- Scan intervallum, tápellátás, adatmennyiség trade-off
- Regisztrált eszközlista user-enként (PostgreSQL)
- RSSI szűrés: csak „közeli" eszközök (szobán belül vs. szomszéd)

### Nyitott kérdések (részletek kidolgozandók)

- [ ] **MAC randomization:** modern telefonok randomizált MAC-et adnak – név alapú azonosítás megbízható-e?
- [ ] **iOS vs Android:** BLE advertising különbségek – mely platformok működnek jól?
- [ ] **Adatvédelem / GDPR:** más emberek BT eszközeinek scan-elése jogilag rendben van-e?
- [ ] **Tasmota vs custom firmware:** BLE scan elérhető-e Tasmotával, vagy külön ESP-IDF build kell?
- [ ] Milyen scan gyakoriság és retention policy?
- [ ] Hány regisztrált eszköz / felhasználó realistic?
- [ ] BLE önálló termék, vagy panic button / gateway eszköz része?
- [ ] Hamis pozitív/negatív: telefon BT kikapcsolva, repülőgép mód – hogyan kezeljük?

---

## 🌀 Okos ventilátor (távolról monitorozható és paraméterezhető)

> Részletes hardver / firmware leírás: [`projekt-ventilator.md`](projekt-ventilator.md)

### Kibővített koncepció (2026-06-07 megbeszélés alapján)

Az alap ventilátor-szabályozás (hőmérséklet → PWM) önállóan is működik Tasmota Rules-szal. A SmartBlue platform két fontos többletértéket ad hozzá:

1. **Távolról látható működés** – a szerver dashboardon látható, hogy a ventilátor megfelelően működik-e (fordulatszám, hőmérséklet, riasztás ha leáll)
2. **Távolról paraméterezhető** – a hőmérséklet-fordulatszám görbe (küszöbök, PWM értékek) távolról állítható, nem kell helyszínre menni

```
Helyszín               SmartBlue szerver
──────────────────     ──────────────────────────────
DS18B20 → ESP32    →   MQTT → InfluxDB → dashboard
PWM ← Tasmota Rules ←  MQTT cmnd → paraméter frissítés
```

### Célalkalmazások
- Ipari szekrény / villamos szekrény hűtése
- Szerverszoba / rack hűtés
- 3D nyomtató hűtése
- Mezőgazdasági eszközök (nyári hőkezelés)

---

## ⚡ Gép teljesítmény monitor

### Koncepció (2026-06-07 megbeszélés alapján)

Nem invazív áramfogyasztás-mérő gépekhez, amely egyszerre teljesít **fogyasztásmérő** és **munkafelügyeleti** szerepet.

```
SCT-013 (áramváltó)
       │ analóg jel
       ▼
   ESP32 + Tasmota
       │ MQTT
       ▼
SmartBlue szerver → InfluxDB → dashboard
```

### Funkciók

| Funkció | Leírás |
|---------|--------|
| **Fogyasztásmérés** | Valós idejű W/kWh mérés gépenként |
| **Áramköltség számítás** | kWh × egységár → napi/havi költség |
| **Munkafelügyelet** | Látható mikor kapcsolták be/ki az egyes gépeket |
| **Üzemóra számláló** | Gépenként összesített üzemidő |
| **Riasztás** | Ha a gép nem kapcsol be/le az elvárt időben |

### Hardver elemek
- ESP32
- SCT-013 áramváltó (nem invazív, csak a kábel köré kell csípni)
- Burden ellenállás + kondenzátor (illesztőkör)
- Opcionális: OLED kijelző helyi megjelenítéshez

### Előnyök
- **Nem invazív** – nem kell a villamos bekötéshez nyúlni
- Meglévő gépekre utólag felszerelhető
- Azonnali ROI: láthatóvá teszi a pazarlást / felesleges üzemeltetést
- Kombinálható a ventilátor-projekttel (egy ESP32-n több szenzor)

### Nyitott kérdések
- [ ] Egyenáramú (DC) vagy váltóáramú (AC) gépek?
- [ ] Hány gép / fázis egyidejű mérése szükséges?
- [ ] Milyen egységárat kell számolni (szerbiai áramár)?
- [ ] Kell-e helyi kijelző a gépen?

---

## 📱 Telepítési segéd – Bluetooth / NFC alapú provisioning

> Ötlet: az első WiFi-konfiguráció elvégzése helyszínen, USB-kábel nélkül, telefon segítségével.

### A probléma

Az ESP32 + Tasmota eszköz telepítésekor valakinek fizikailag ott kell lennie egy laptoppal (Tasmota Manager) vagy soros kábellel. Bluetooth vagy NFC segíthetne a „last-mile" beüzemelésben: a szerelő telefonjával azonnal beállítja a WiFi-t, MQTT-t.

---

### 1. lehetőség – Tasmota AP mód (már most működik, app sem kell)

Tasmota első induláskor saját WiFi AP-t nyit (`tasmota-XXXX`, 192.168.4.1). A szerelő telefonjával csatlakozik ehhez az AP-hoz, böngészőben beállítja a WiFi + MQTT adatokat. **Nincs szükség extra hardverre vagy appra.** Ez az azonnal használható megoldás.

**Korlát:** a webes UI alap Tasmota, nem SmartBlue-specifikus (nincs user/region/device_id mező).

---

### 2. lehetőség – NFC tag az eszközön

Az eszközre egy programozható NFC tag kerül. A telepítő telefona az NFC tagot megtapogatva kap egy URL-t vagy konfigurációs adatot.

#### NFC tag tartalmak (alternatívák)

| Tartalom | Leírás | Ami kell hozzá |
|----------|--------|----------------|
| URL → SmartBlue webes konfigurátor | A tag egy `https://smartblue.io/setup?device=AABBCC` URL-t tartalmaz → telefon böngészőben megnyílik a konfigurációs oldal | Webes konfigurátor backend |
| URL → Tasmota AP webes UI | `http://192.168.4.1` (csak akkor, ha a telefon csatlakozva van az eszköz AP-jához) | Semmi extra |
| NDEF szöveg → device ID + típus | Tag tartalmazza a MAC-et és board típust → app automatikusan kitölti a regisztrációs mezőket | SmartBlue app vagy PWA |

#### Hardver igény az NFC-hez

- Passzív NFC tag (pl. NTAG213, ~5 Ft/db) az eszközre ragasztva
- Nincs szükség NFC-olvasóra az ESP32-n (a telefon olvassa a tag-et)
- Az ESP32-nek opcionálisan lehet aktív NFC olvasója (PN532 modul), de ez nem feltétlenül szükséges

---

### 3. lehetőség – Bluetooth (BLE) provisioning

#### ESP-Touch / SmartConfig (WiFi provisioning BLE-vel, Tasmota támogatja)

Tasmota tartalmaz `SmartConfig` (`SetOption65`) módot: telefon BLE-n vagy broadcast csomagokon keresztül küldi a WiFi SSID-t és jelszót az ESP32-nek, **anélkül hogy előbb csatlakozna az AP-hoz**. Ehhez léteznek kész mobilappok (pl. Espressif ESPTouch app, Android + iOS).

**Korlát:** csak WiFi adatokat küld, MQTT + user/region + device_id nem konfigurálható így.

#### Dedikált SmartBlue BLE konfigurátor app

Egyedi mobilapp (React Native / Flutter vagy PWA), amely:
1. BLE-n csatlakozik az ESP32-re (egyedi Tasmota build vagy firmware extension szükséges)
2. Elküldi a teljes SmartBlue konfigurációt (WiFi + MQTT + user/region/device_id)
3. Regisztrálja az eszközt a SmartBlue backend-ben

**Fejlesztési igény:** jelentős (egyedi firmware + mobilapp), de prémium telepítési élményt ad.

---

### 4. lehetőség – QR kód a webes konfigurátorhoz

Az eszközre nyomtatott QR kód → SmartBlue webes konfigurátor előre kitöltve a device MAC-del. Nem igényel extra hardvert, csak a webes konfigurátor backend-et. Mobilon is működik.

---

### Összehasonlítás

| Megoldás | Fejlesztési igény | Hardver | Felhasználói élmény | Javaslat |
|----------|-------------------|---------|---------------------|----------|
| Tasmota AP mód | Semmi | Semmi | Közepes (kézi lépések) | **Azonnal bevezethető** |
| NFC tag (URL) | Webes konfigurátor kell | Passzív NFC tag (~5 Ft) | Jó (tapintás → böngésző) | **2. prioritás** |
| QR kód | Webes konfigurátor kell | Semmi (nyomtatás) | Jó | **2. prioritás** |
| BLE SmartConfig | Minimális | Semmi | Közepes | Csak WiFi-t old meg |
| BLE + egyedi app | Nagy (firmware + app) | Semmi | Prémium | Jövőbeli lehetőség |

### Javasolt irány

**Rövidtávon:** a Tasmota AP mód elegendő a pilot fázishoz.

**Középtávon:** webes konfigurátor (SmartBlue webUI) + QR kód / NFC tag kombinációja. A webUI egyben a mobil telepítési eszköz is – nincs szükség natív appra. PWA formában offline is működhet.

**Hosszútávon:** ha a telepítők száma nő, BLE-alapú provisioning app megfontolandó a prémium UX-ért.

### Nyitott kérdések

- [ ] Lesz-e dedikált SmartBlue webes konfigurátor (a Tasmota Manager TUI webes változata)?
- [ ] Az NFC tag tartalmát az gyártás/programozás során töltik fel, vagy helyszínen?
- [ ] Szükséges-e offline provisioning (helyszínen nincs internet)?
- [ ] Melyik szerepkör végzi a telepítést – Robi/Alfréd szakemberek vagy az ügyfél?

---

## 🤖 AI agent – szenzoradatok feldolgozása, következtetések és előrejelzések

> Ötlet (2026-06-21): a kihelyezett szenzorokból érkező adatokat AI agent-tel dolgozzuk fel, és a beérkező mérésekből következtetéseket, előrejelzéseket vonunk le.

> **Megvalósítási elv:** az LLM chat **csak adatmegjelenítő réteg** – a dashboard alternatívája, nem helyettesíti a szabályzást vagy eszközvezérlést. Részletek: [`megvalositasi-terv.md`](megvalositasi-terv.md). **1. fázisban még nincs LLM UI** – előbb adatgyűjtés.

### Első jelölt: Hermes Agent

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) az első vizsgált megoldás – nyílt forráskódú AI agent keretrendszer, amely eszközökhöz és adatforrásokhoz csatlakozva képes elemzést és válaszadást végezni.

```
Szenzorok → MQTT → InfluxDB / PostgreSQL
                         │
                         ▼
                   Hermes Agent  ←── felhasználói kérdések (chat)
                         │
                         ▼
              következtetések, előrejelzések, riasztások
```

### Kulcs követelmény: felhasználónkénti adatelkülönítés

**Minden usert külön kell kezelni** – amikor a Hermes válaszol a kérdésekre, csak az adott felhasználó saját szenzoradatait lássa. Ez multi-tenant architektúrát igényel:

| Terület | Kihívás |
|---------|---------|
| Adatbázis lekérdezések | InfluxDB / PostgreSQL lekérdezések user_id szerint szűrve |
| Agent kontextus | A Hermes session / tool hívások ne férjenek hozzá más user adataihoz |
| Eszköz azonosítás | MQTT topic struktúra (`{user_id}/{regio_id}/...`) összhangban az agent hozzáféréssel |

### AI-alapú paraméterezés + Node-RED

Jó lenne, ha az eszközök **paraméterezését is az AI tudná végezni** (pl. „állítsd a ventilátor küszöböt 28 °C-ra"), esetleg **Node-RED flow-kkal kiegészítve** az automatizálást.

Ugyanaz a multi-user probléma merül fel: Node-RED-ben is meg kell oldani, hogy minden felhasználó csak a saját flow-jait és eszközeit érje el.

### Első lépés – otthoni adatgyűjtés (Viktor)

Mielőtt éles pilot indul, **otthon minél több eszközt és szenzort üzembe helyezni**, és elkezdeni az adatok gyűjtését – így kiderül, mit tud velük kezdeni az AI (mintaadatok, minta kérdések, korai prototípus).

### Nyitott kérdések

- [ ] Hermes Agent self-hosted vs. felhő – hol fut, milyen LLM backend?
- [ ] Hogyan kötjük össze a Hermes tool-okat az InfluxDB / FastAPI API-val?
- [ ] Node-RED integráció: külön instance user-enként, vagy egy instance tenant-szűréssel?
- [ ] Milyen típusú kérdések / előrejelzések a legértékesebbek az első pilotban?
- [ ] Adatvédelem: az LLM-nek milyen adatmennyiséget szabad átadni (GDPR)?
- [ ] **Szokásprofil / anomália detekció:** panic button + jelenlét + BLE adatokból – milyen algoritmus / prompt?
- [ ] BLE scan adatok tárolása és user-enkénti eszköz-whitelist kezelése

---

## 🌾 Mezőgazdasági alkalmazás (pilot lehetőség)

> Továbbra is számolunk a mezőgazdasági alkalmazás lehetőségével. A pilot projektet valószínűleg **Ervinnel** fogjuk megcsinálni. **Gilvázi Istvánnál** is lehetne egy minta projekt – fólia sátras termelésben van benne, valószínűleg tudna hasznos ötleteket adni a terepi igényekről.

### Lehetséges pilot helyszínek

| Személy | Háttér | Szerep a pilotban |
|---------|--------|-------------------|
| **Ervin** | Mezőgazdaság | Valószínű első pilot partner |
| **Gilvázi István** | Fólia sátras termelés | Minta projekt helyszín; domain szakértelem, ötletek a mérési/vezérlési igényekről |

### Koncepció

Terepi szenzorokkal mért földtulajdonságok (pl. **talajnedvesség**, hőmérséklet) kiegészíthetők **nyilvános meteorológiai adatokkal** (csapadék, hőmérséklet, páratartalom előrejelzés) – így az AI agent összetettebb következtetéseket tud levonni (pl. öntözési javaslat, betegség-kockázat).

```
Talajnedvesség szenzor ──┐
Hőmérséklet szenzor    ──┼──► SmartBlue szerver ──► AI agent
                         │         ▲
Nyilvános meteo API  ────┘         └── Ervin / Gilvázi István pilot helyszín
```

### Nyitott kérdések

- [ ] Ervin pilot helyszínének pontosítása
- [ ] Gilvázi István – fólia sátras minta projekt: milyen szenzorok/vezérlések lennének hasznosak?
- [ ] Mely meteorológiai API-k érhetők el Szerbiában ingyenesen?
- [ ] Milyen szenzorok kellenek? → **RS485 3-in-1** (nedvesség + talaj hő + EC), nem csak kapacitív nedvesség
- [ ] GSM 4G szükséges-e a mezőgazdasági helyszínen (nincs WiFi)?

---

## ⚡ Háromfázisú teljesítménymérő – minta áramkör (Zöldi)

> Zsolti összerak egy **minta áramkört**, amely **három fázis teljesítményét** méri, és **Zöldinél** fogja beüzemelni.

Ez a „Gép teljesítmény monitor" ötlet kiterjesztése többfázisú (3×230V) ipari / háztartási mérésre. A minta áramkör célja: a mérési elv validálása valós környezetben, mielőtt sorozatgyártásba menne.

### Nyitott kérdések

- [ ] Milyen szenzor / IC (pl. PZEM-004T, ADE7953, SCT-013 × 3)?
- [ ] Egy ESP32-n hány fázis mérhető egyszerre?
- [ ] Zöldi helyszín: milyen gépek / fogyasztók lesznek mérve?

---

## További termék ötletek (jövőre)

| Ötlet | Leírás |
|-------|--------|
| Levegőminőség állomás | CO₂ + hőmérséklet + pára, irodai / iskolai telepítésre |
| Okos kapcsoló | Meglévő villanykapcsolóba épülő ESP32 modul |
| Növényöntöző | Talajnedvesség + szivattyúvezérlés |
| Idős felügyelet (panic + jelenlét + BLE) | Nyomógomb + LD2410C + opcionális BLE scan, AI szokásprofil |
