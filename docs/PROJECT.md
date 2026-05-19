# SmartBlue – Projekt kontextus

## Áttekintés

A SmartBlue egy IoT eszközcsalád fejlesztési projektje, amelynek célja terepi adatgyűjtő eszközök és azokat kiszolgáló szerveroldali szoftver együttes megvalósítása.

Az első pilot projektek **Szerbiában** kerülnek telepítésre.

---

## Terepi eszközök

### Platform
- **Mikrokontroller:** ESP32 (Espressif)
- **Közös kommunikációs modul:** minden eszközváltozatban azonos kommunikációs réteg

### Eszközcsalád struktúrája
Az eszközcsalád tagjai eltérő mérési/vezérlési feladatot látnak el, de a kommunikációs rész közös — ez lehetővé teszi az egységes szerver-oldali kezelést és a közös firmware-alapot.

### Kommunikációs módok

| Módszer | Leírás |
|--------|--------|
| **WiFi** | IEEE 802.11 b/g/n, helyi hálózaton vagy hotspot-on keresztül |
| **GSM 4G** | Mobilhálózati kapcsolat (LTE Cat-M1 / NB-IoT / full 4G modul) |

→ Részletes összehasonlítás: [`kommunikacio.md`](kommunikacio.md)

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
| `szerver-architektura.md` | Szerver technológiai lehetőségek |
| `dontes-elokeszito.md` | Összefoglaló döntési mátrix |
