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

---

## Dokumentumtérkép

| Fájl | Tartalom |
|------|----------|
| `PROJECT.md` | Ez a fájl – projekt kontextus |
| `kommunikacio.md` | WiFi vs GSM 4G összehasonlítás, döntési szempontok |
| `szerver-architektura.md` | Szerver technológiai stack és architektúra |
| `mqtt-protokoll.md` | MQTT topic struktúra (Tasmota konvenció) |
| `eszkoz-szenzorok.md` | ESP32 szenzor katalógus és eszközcsalád tervezés |
| `dontes-elokeszito.md` | Összefoglaló döntési mátrix |
