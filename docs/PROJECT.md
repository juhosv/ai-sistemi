# SmartBlue – Projekt kontextus

## Áttekintés

A SmartBlue egy IoT eszközcsalád fejlesztési projektje, amelynek célja terepi adatgyűjtő eszközök és azokat kiszolgáló szerveroldali szoftver együttes megvalósítása.

Az első pilot projektek **Szerbiában** kerülnek telepítésre.

---

## Csapat

| Szereplő | Szerepkör |
|---------|-----------|
| **Viktor** | How-to, projekt koordináció, követelmények |
| **Zsolti (Sogi)** | Hardware tervezés és gyártás (Szerbiában él, helyi pilot felelős) |
| **Bálint** | Szerver oldal: adatbázis és UI fejlesztés |

### Külső közreműködők (potenciális)

| Személy | Háttér | Szerep |
|---------|--------|--------|
| **Robi** | Riasztórendszerek szerelése | Helyszíni üzembe helyezés és üzemeltetés; saját szervere van |
| **Alfréd** | Diák, kamera-rendszerek szerelése | Helyszíni üzembe helyezés és üzemeltetés |

> Az első eszközöket várhatóan ők helyezik üzembe és üzemeltetik.  
> Robinak van egy szervere – Bálint megvizsgálja, hogy alkalmas-e a SmartBlue stack-hez.

---

## Projekt jelenlegi fázisa

**Információgyűjtés és pilot előkészítés**

- Az összes projektinformáció markdown fájlokban kerül rögzítésre ebben a mappában
- Elsődleges cél: a tudásbázis felépítése és a döntések dokumentálása
- A pilot projekt indulásához szükséges döntések és feladatok nyomon követése: [`dontes-elokeszito.md`](dontes-elokeszito.md)

---

## Terepi eszközök

### Platform
- **Mikrokontroller:** ESP32 (Espressif)
- **Közös kommunikációs modul:** minden eszközváltozatban azonos kommunikációs réteg

### Eszközcsalád struktúrája
Az eszközcsalád tagjai eltérő mérési/vezérlési feladatot látnak el, de a kommunikációs rész közös — ez lehetővé teszi az egységes szerver-oldali kezelést és a közös firmware-alapot.

### Firmware
- **Tasmota** – nyílt forráskódú ESP32/ESP8266 firmware
- MQTT kommunikáció Tasmota konvenció szerint: `cmnd/`, `stat/`, `tele/` prefix struktúra

### Kommunikációs módok

| Módszer | Leírás |
|--------|--------|
| **WiFi** | IEEE 802.11 b/g/n, helyi hálózaton vagy hotspot-on keresztül |
| **GSM 4G** | Mobilhálózati kapcsolat (LTE Cat-M1 / NB-IoT / full 4G modul) |

→ Részletes összehasonlítás: [`kommunikacio.md`](kommunikacio.md)  
→ MQTT topic struktúra: [`mqtt-protokoll.md`](mqtt-protokoll.md)

---

## Szerveroldali szoftver

A szerver a következő fő feladatokat látja el:

1. **Adatgyűjtés** – eszközök adatainak fogadása és tárolása
2. **Adatfeldolgozás** – nyers adatok értelmezése, aggregálása, elemzése
3. **Konfiguráció kezelés** – eszközök konfigurációjának előállítása
4. **OTA konfig letöltés** – konfiguráció automatikus kijuttatása az eszközökre
5. **Hibafigyelés** – meghibásodott vagy nem elérhető eszközök detektálása
6. **Értesítések** – felhasználók értesítése:
   - Email
   - SMS
   - Push üzenet (mobilalkalmazás vagy web push)

→ Részletes lehetőségek: [`szerver-architektura.md`](szerver-architektura.md)

---

## Pilot projekt

- **Helyszín:** Szerbia
- **Cél:** Az eszközcsalád és a szerver infrastruktúra első éles tesztelése

### Teszt fázis (jelenlegi)

- **Teszt eszköz:** Wemos D1 Mini (ESP8266) – egyszerűbb, olcsóbb, a végleges ESP32 előtt
- **Teszt szerver:** Bálint beállított egy ingyenes MQTT bróker + email értesítő szervert
- **Folyamat:** Sogi megkapja a Tasmota telepítési leírást + szerver MQTT beállításokat → D1 Mini csatlakozik → email értesítés megy
- **Eszközök a teszt után:** Végleges ESP32-alapú hardver tervezése (Sogi feladata)

---

## Eszközfilozófia

> **Nem nagyon általános, hanem sok különböző – de azonos alapokon.**

Az eszközcsalád tagjai specifikus feladatokra optimalizált eszközök, nem univerzális platformok. Az egységes kommunikációs és firmware alap (ESP32 + Tasmota + MQTT) teszi lehetővé a könnyű bővítést és a közös szerver-oldali kezelést.

---

## Infrastruktúra tervek

- **GitHub:** A projekt átkerül GitHub-ra – így Zsolti, Robi és Alfréd is könnyen hozzáfér a dokumentumokhoz és fájlokhoz
- **Obsidian:** A dokumentáció Obsidian-ban szerkesztve, Git pluginnal szinkronizálva → szépen renderelt MD fájlok mindenki számára
- **Projektmenedzsment:** Eszköz kiválasztása folyamatban (GitHub Projects, Linear, Notion stb.)

---

## Dokumentumtérkép

| Fájl | Tartalom |
|------|----------|
| `PROJECT.md` | Ez a fájl – projekt kontextus |
| `kommunikacio.md` | WiFi vs GSM 4G összehasonlítás, döntési szempontok |
| `szerver-architektura.md` | Szerver technológiai stack és architektúra |
| `mqtt-protokoll.md` | MQTT topic struktúra (Tasmota konvenció) |
| `eszkoz-szenzorok.md` | ESP32 szenzor katalógus és eszközcsalád tervezés |
| `hw-d1mini-tasmota.md` | D1 Mini Tasmota telepítés, MQTT és PIR konfiguráció |
| `termek-otletek.md` | Termék ötletek és koncepciók |
| `beszerzes.md` | Megvásárolt alkatrészek listája |
| `projekt-ventilator.md` | Hőmérsékletfüggő ventilátor-szabályozó projekt |
| `hw-kijelzok.md` | Kijelző opciók – SSD1306, TFT, e-paper (Tasmota kompatibilitás) |
| `hw-gyartok-tasmota.md` | Tasmota-kompatibilis gyártók (Athom, Nous, Shelly, Sonoff stb.) |
| `dontes-elokeszito.md` | Összefoglaló döntési mátrix |
