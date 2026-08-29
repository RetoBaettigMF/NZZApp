# Changelog

## [3.0.0] - 2026-08-29

### Geändert
- **Scraper komplett überarbeitet.** Aus der 797-Zeilen-Datei `backend/scraper.py`
  wurde das Paket `backend/nzz_scraper/` mit Page-Models, Sensor-Schicht und
  Mobilgerät-Emulation. Einstieg jetzt `python run_scraper.py`.
- Browser läuft im Profil `Pixel 7` (`locale=de-CH`, `timezone=Europe/Zurich`);
  die mobilen NZZ-Seiten sind einfacher strukturiert.
- Login-Session wird in `backend/.state/` persistiert (Modus 0600) und nur bei
  Bedarf erneuert – ein Lauf braucht damit 1.5s statt 6s für die Anmeldung.
- Alle festen Wartezeiten durch Zustandsprüfungen ersetzt.
- `print()` durch das `logging`-Modul mit rotierender Datei ersetzt.

### Behoben
- Ein fehlgeschlagener Login galt als Erfolg und der Lauf scrapte still anonym
  weiter. Jetzt: Exit-Code 2.
- Der Artikel-Container wurde über `article` gesucht – mobil sind das 320 Zeichen
  Teaser statt 6500 Zeichen Fliesstext (`section.container--article`).
- Paywall-Anrisse wurden gespeichert *und* getrackt und deshalb nie erneut
  versucht. Jetzt werden sie erkannt und übersprungen.
- Die Extraktion griff den Text ab, bevor Piano über den Zugriff entschieden
  hatte. Jetzt wird der Entscheid abgewartet.
- `/information/impressum-ld.148422` wurde als Artikel eingesammelt.
- HTTP 403/429 waren unsichtbar, weil die `goto()`-Response verworfen wurde.
- Falscher Pfad in `nzz-scraper-sync.sh` (`Development` statt `development`).

### Hinzugefügt
- **NZZ-Pro-Artikel werden übersprungen, wenn das Abo sie nicht abdeckt.**
  NZZ hat zwei Abostufen; Pro-Artikel sind über
  `<meta name="mrf:tags">` (`Content Type:Pro Article`) und über die
  Teaser-Markierung im Feed erkennbar (geprüft: 8/8 Übereinstimmung). Fehlt
  das Pro-Abo, werden sie bereits anhand des Feeds aussortiert – die Seite wird
  gar nicht erst geladen. Ohne das würden sie bei jedem Lauf neu geholt,
  als Paywall verworfen und mangels Tracking endlos wiederholt.
  Die Abostufe ermittelt der Scraper selbst (ein Pro-Artikel als Stichprobe,
  Längenvergleich mit den Standard-Artikeln desselben Laufs) und merkt sie in
  `backend/.state/nzz_entitlement.json`; nach sieben Tagen prüft er neu, damit
  ein Upgrade auffällt. Steuerbar über `--pro-access auto|yes|no`,
  `--recheck-pro` bzw. `NZZ_PRO_ACCESS` und `NZZ_PRO_RECHECK_DAYS`.
- Live-Smoke-Test `tests/scraper_smoke_test.py`.
- `python -m nzz_scraper.tools.explore` zum Neuermitteln der Selektoren.
- Debug-Artefakte (Screenshot, HTML, Sensorwerte) unter `backend/debug/`.

## [2.0.0] - 2026-02-19

### 🔐 Authentication System

**Backend:**
- Flask-Server mit JWT-Authentication
- bcrypt Password-Hashing
- User-Management API
- Protected Endpoints

**Frontend:**
- Login-Page
- AuthContext
- AdminPanel (User-Verwaltung)
- UserMenu (Passwort ändern, Logout)

### ✨ UI Improvements

- Lesefortschritt-Tracking
- "Gelesene ausblenden" Toggle
- Hamburger-Menü
- "Neuester Artikel" Button
- Einheitliches Button-Design

### 🐛 Bugfixes

- DateNavigator Richtung korrigiert
- Artikel-Zähler bei ausgeblendeten Artikeln
- Doppelte Titel entfernt

---

## [1.0.0] - 2026-02-18

### Initial Release

- NZZ Artikel Scraper
- Offline-PWA
- ArticleReader
- DateNavigator
- LocalStorage Support
