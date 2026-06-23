---
kanban-plugin: board
---

## todo

- [ ] Otthoni adatgyűjtés – Viktor: minél több eszköz/szenzor üzembe helyezése (AI kísérletekhez)
- [ ] **Beszerzés:** Hestore MAX485-M (+ opc. USB-RS485) – talaj szonda RS485 illesztéshez
- [x] **Beszerzés:** Hestore SOIL-H-T-EC-RS485 (2026-06-23)
- [x] **Beszerzés:** Hestore LD2410C × 4 jelenlét érzékelő (2026-06-23)
- [ ] Szerver vásárlás intézése – Zsolti
- [ ] Honlap összeállítása – Bálint (korábbi munkák leírásával)
- [ ] Domain név kiválasztása – `.rs` végződés
- [ ] Háromfázisú teljesítménymérő minta áramkör – Zsolti → Zöldinél beüzemelés
- [ ] Mezőgazdasági pilot előkészítés – Ervinnel; Gilvázi István fólia sátras minta projekt
- [ ] AI agent (Hermes) multi-tenant architektúra megtervezése
- [ ] AI paraméterezés + Node-RED multi-user megoldás vizsgálata
- [ ] Panic button kibővítés – LD2410C jelenlét + AI szokásprofil
- [ ] BLE személy-érzékelés ötlet kidolgozása (scan, whitelist, adatvédelem)
- [ ] IoT router modell kiválasztása – előre konfigurált, ügyfélnek (több projekt esetén)
- [ ] Email értesítés Soginak Switch/PIR eseményre (`zsoltorigo@gmail.com`)
- [ ] PIR szenzor éles teszt (Sogi helyszínen)
- [ ] MVP scope meghatározása – 1. fázis: adatgyűjtés + dashboard
- [ ] Felhasználói napló API + beviteli felület (1. fázis)
- [ ] Meteorológiai API integráció (1. fázis – külső adatforrás)
- [ ] Grafana / dashboard – szenzor adatok megjelenítése
- [ ] EMQX autentikáció – eszköz azonosítási módszer kiválasztása
- [ ] Dashboard döntés – Grafana, egyedi UI, vagy csak riasztás?
- [ ] Mobilalkalmazás döntés – web UI, PWA vagy natív app?
- [ ] GDPR / adatvédelem – szerbiai vs EU adattárolás jogi vizsgálata
- [ ] Eszközcsalád pontosítása – ismert: hőmérséklet/pára, relé, mozgásérzékelő; további típusok nyitottak
- [ ] Szerver (FastAPI + EMQX + PostgreSQL + InfluxDB) implementáció – Bálint


## in progress

- [ ] **1. fázis** – adatgyűjtés, feldolgozás, dashboard ([`megvalositasi-terv.md`](megvalositasi-terv.md))
- [ ] Tasmota Manager TUI – hibajavítások és stabilitás (board oszcilláció, config fetch)
- [ ] Pilot előkészítés – Sogi helyszíni eszközök tesztelése


## testing

- [ ] Tasmota Manager – config letöltés (GPIO port beállítások megjelenése)
- [ ] Tasmota Manager – board típus oszcilláció javítás (Mem1 vs chip-default)


## done

- [x] Szerver stack döntés: EMQX + FastAPI + PostgreSQL + InfluxDB
- [x] Kommunikáció döntés: WiFi pilot, GSM 4G (1NCE SIM) következő fázis
- [x] MQTT topic struktúra: `{user_id}/{regio_id}/{topic}/{prefix}/`
- [x] TelePeriod: 300 mp (konstans a kódban)
- [x] End-to-end teszt sikeres – Sogi eszköze (`kzs_smart_proba_2026`) MQTT üzenetet küld
- [x] Tasmota telepítési leírás elkészült → Sogi megkapta
- [x] Teszt szerver kész (Bálint) – MQTT broker + email értesítő
- [x] Tasmota Manager – Flash tab (firmware letöltés + esptool égetés)
- [x] Tasmota Manager – Serial Monitor tab (élő soros kimenet, parancsküldés)
- [x] Tasmota Manager – Config tab (WiFi, MQTT, GPIO konfiguráció küldés)
- [x] Tasmota Manager – MQTT Monitor tab (broker kapcsolat, topic fa, payload viewer)
- [x] Tasmota Manager – Board tab (vizuális pin térkép, élő állapot)
- [x] Tasmota Manager – Config backup/restore HTTP-n (.dmp fájl parse)
- [x] Tasmota Manager – Board diagram: ismert eszközök GPIO kiosztása (Sonoff 4CH stb.)
- [x] Tasmota Manager – User/Region szerkesztő (user-first hierarchia)
- [x] Tasmota Manager – MQTT ID sanitizáció (szóköz → _, tiltott karakterek eltávolítása)
- [x] Tasmota Manager – Board típus tárolás Mem1-ben, auto-kijelzés Board tabon
- [x] Tasmota Manager – TelePeriod és board mezők összevonása/egyszerűsítése




%% kanban:settings
```
{"kanban-plugin":"board","list-collapse":[false,false,false,false]}
```
%%
