---

kanban-plugin: board

---

## todo

- [ ] Email értesítés Soginak Switch/PIR eseményre (`zsoltorigo@gmail.com`)
- [ ] PIR szenzor éles teszt (Sogi helyszínen)
- [ ] MVP scope meghatározása – mi kell az első pilot induláshoz minimálisan
- [ ] EMQX autentikáció – eszköz azonosítási módszer kiválasztása
- [ ] Dashboard döntés – Grafana, egyedi UI, vagy csak riasztás?
- [ ] Mobilalkalmazás döntés – web UI, PWA vagy natív app?
- [ ] GDPR / adatvédelem – szerbiai vs EU adattárolás jogi vizsgálata
- [ ] Eszközcsalád pontosítása – ismert: hőmérséklet/pára, relé, mozgásérzékelő; további típusok nyitottak
- [ ] Szerver (FastAPI + EMQX + PostgreSQL + InfluxDB) implementáció – Bálint


## in progress

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
