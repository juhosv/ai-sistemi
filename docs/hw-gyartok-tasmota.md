# Tasmota-kompatibilis gyártók és márkák

> Referencia vásárláshoz: gyárilag Tasmotával érkező, vagy könnyen flashelhető eszközök gyártói.

---

## Gyárilag Tasmotával érkező gyártók

Ezek a cégek kimondottan nyílt firmware rajongóknak gyártanak – a webáruházban opcióként választható a Tasmota előre telepítve.

| Gyártó | Székhely | Termékek | Megjegyzés |
|--------|----------|----------|------------|
| **Athom** | – | Okoskonnektor (fogyasztásméréssel), okosizzó, fali kapcsoló, LED-vezérlő | Legismertebb, legszélesebb választék |
| **Nous** | Lengyel (EU) | Konnektor sorozatok, pl. Nous A8T | Európai, Tasmota előre telepített szériák |
| **LocalBytes** | Angol (UK) | Okoskonnektor, relé | Nagy választék, előre flashelt eszközök |
| **Martin Jerry** | – | Fali kapcsoló, dimmer (fényerőszabályzó) | Tasmota előre telepített verzióban elérhető |

---

## Tasmotára cserélést támogató gyártók

Gyárilag saját firmware, de a hardver kialakítása miatt könnyen lecserélhető – forrasztás nélkül.

### Shelly (Allterco)

- Prémium kategóriás európai relé és kapcsoló gyártó
- Gyárilag saját szoftver + MQTT helyi vezérlés támogatással
- ESP-alapú (régebbi) modellek + ESP32-es (újabb) modellek
- Tasmota telepítés: **OTA (Over-The-Air)** – forrasztás nélkül
- **Figyelj rá:** újabb Shelly generációknál (Shelly Gen2/Gen3) a Tasmota telepítés eltérő módszert igényel – mindig ellenőrizd a Supported Devices listát vásárlás előtt

### Sonoff (ITEAD)

- Széles termékskála, olcsó ESP-alapú reléktől kezdve
- **DIY Mode** támogatású modellek (pl. Sonoff Basic R3, Mini): hivatalosan engedélyezi külső firmware feltöltését az eWeLink felhő megkerülésével
- Tasmota közösségben a legelterjedtebb flashelt márka

---

## Hasznos adatbázisok vásárlás előtt

> A gyártók időről időre változtatják a hardver komponenseket – egy típus belső chipje lecserélhető flashelés nélküli verzióra! Mindig ellenőrizd a listákat vásárlás előtt.

| Forrás | Link | Mire jó |
|--------|------|---------|
| **Tasmota Supported Devices** | https://templates.blakadder.com | Gyárilag Tasmotával érkező eszközök teljes listája |
| **Tasmota Device List** | https://tasmota.github.io/docs/Supported-Peripherals/ | Kompatibilis és támogatott modulok, perifériák |

---

## Relevancia a SmartBlue projekthez

A SmartBlue platform szempontjából ezek az eszközök különösen érdekesek:

| Felhasználás | Javasolt eszköz típus | Gyártó |
|-------------|----------------------|--------|
| Kész konnektor / fogyasztásmérő | Okoskonnektor Tasmotával | Athom, Nous, LocalBytes |
| Fali kapcsoló csere | Tasmota fali kapcsoló | Martin Jerry, Sonoff |
| Relé modul (saját dobozba) | Sonoff Basic / Mini DIY Mode | Sonoff |
| Prémium relé, helyi MQTT | Shelly relé | Shelly |

> **Pilot stratégia:** Az első pilot projektekben érdemes lehet kész Tasmotás eszközöket (pl. Athom konnektor) használni a saját ESP32 hardver párhuzamos fejlesztése mellett – gyorsabb telepítés, kevesebb kockázat.
