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

## További termék ötletek (jövőre)

| Ötlet | Leírás |
|-------|--------|
| Levegőminőség állomás | CO₂ + hőmérséklet + pára, irodai / iskolai telepítésre |
| Okos kapcsoló | Meglévő villanykapcsolóba épülő ESP32 modul |
| Növényöntöző | Talajnedvesség + szivattyúvezérlés |
