# Termék ötletek

> Ötletek, amelyek a SmartBlue platform alapján megvalósíthatók. Nem végleges roadmap – inkább inspirációs lista és lehetséges irányok.

---

## 💡 Konnektoros „panic button" eszköz

### Koncepció

Egy konnektorba dugható kis doboz, amelyen egyetlen nyomógomb van. Megnyomáskor értesítést küld a beállított személyeknek (hozzátartozók, gondozók stb.).

### Célcsoport
- **Elsődleges:** Idős emberek, akik egyedül élnek
- **Másodlagos:** Betegek, gyengélkedők, gyerekek felügyelete
- **Intézményi:** Idősotthon, gondozási intézmény

### Hogyan működne

```
1. Eszköz konnektorba dugva → folyamatos táplálás, WiFi kapcsolat
2. Felhasználó megnyomja a gombot
3. ESP32 MQTT üzenetet küld a szervernek
4. Szerver értesítést küld a hozzátartozóknak:
   - Push üzenet (mobilapp / Telegram)
   - SMS
   - Email
5. Opcionális: visszajelzés az eszközön (LED, hangjelzés)
```

### Hardver elemek
- ESP32 (WiFi beépített)
- 1 db nyomógomb (vagy több: SOS + OK/Megvagyok)
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
- Egyszerű használat (1 gomb)
- Nem kell mobiltelefon / tablet az idős embernek
- Olcsón legyártható az ESP32 platform miatt
- A SmartBlue szerver infrastruktúra azonnal használható

### Nyitott kérdések
- [ ] WiFi helyett GSM legyen-e? (WiFi: olcsóbb, de router kell; GSM: önálló, de SIM kell)
- [ ] Milyen értesítési csatorna a legfontosabb? (SMS, push, Telegram?)
- [ ] Kell-e visszajelzés az eszközön a sikeres küldésről? (LED / hang)
- [ ] Legyen-e „check-in" funkció (napi OK gomb)?
- [ ] Intézményi vagy otthoni piac az elsődleges?

---

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

## További termék ötletek (jövőre)

| Ötlet | Leírás |
|-------|--------|
| Levegőminőség állomás | CO₂ + hőmérséklet + pára, irodai / iskolai telepítésre |
| Okos kapcsoló | Meglévő villanykapcsolóba épülő ESP32 modul |
| Növényöntöző | Talajnedvesség + szivattyúvezérlés |
