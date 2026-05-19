# Kommunikációs lehetőségek – WiFi vs GSM 4G

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

## Hibrid megközelítés

Megfontolandó, hogy az eszközcsalád **mindkét módot támogassa** – az eszköz konfiguráció alapján döntsön:
- Ha WiFi elérhető → WiFi-n kommunikál (energia-hatékony)
- Ha WiFi nem elérhető → GSM 4G-n kommunikál (fallback)

Ez növeli a hardver komplexitást, de maximális flexibilitást biztosít.

---

## Összehasonlító táblázat

| Szempont | WiFi | GSM 4G |
|---------|------|--------|
| Hardverköltség | Alacsony | Közepes-magas |
| Üzemeltetési költség | Alacsony | Közepes (SIM díj) |
| Infrastruktúra igény | WiFi hálózat | Mobilhálózat lefedettség |
| Terepi alkalmazás | Korlátozott | Kiváló |
| Áramfogyasztás | Alacsony | Magasabb |
| Sebesség | Nagy | Közepes (IoT módban kicsi) |
| Megbízhatóság | Hálózattól függ | Operátortól függ |
| Fejlesztési bonyolultság | Alacsony | Közepes |

---

## Nyitott kérdések / döntési pontok

- [ ] Milyen helyszíneken kerülnek telepítésre az első pilot eszközök? (beltér/kültér)
- [ ] Van-e helyi WiFi infrastruktúra a pilot helyszíneken?
- [ ] Mekkora az akkumulátor-élettartam elvárás?
- [ ] Melyik szerb mobiloperátorral lesz SIM szerződés?
- [ ] NB-IoT / Cat-M lefedettség megvan Szerbiában a kívánt területeken?
