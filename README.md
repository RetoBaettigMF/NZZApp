# 📰 NZZ Reader

Eine moderne Progressive Web App (PWA) zum Lesen von NZZ-Artikeln mit Offline-Support und Authentifizierung.

## ✨ Features

### Für alle Benutzer:
- 📱 **Progressive Web App** - Installierbar auf Desktop und Mobile
- 🔐 **Sicheres Login-System** - JWT-basierte Authentifizierung
- 📖 **Artikel-Reader** - Optimiert für Lesbarkeit mit Swipe-Navigation
- 💾 **Offline-Support** - Artikel im LocalStorage speichern
- 🗓️ **Datums-Navigation** - Durch Tage navigieren
- ✅ **Lesefortschritt** - Artikel automatisch als gelesen markieren
- 👁️ **Gelesene ausblenden** - Optional bereits gelesene Artikel verstecken
- ⭐ **Artikel markieren** - Wichtige Artikel mit Stern kennzeichnen
- 🤖 **AI-Zusammenfassung** - Doppeltipp auf Artikel schaltet zwischen Original und KI-Zusammenfassung (50–100 Wörter) um
- 🔑 **Passwort ändern** - Eigenes Passwort jederzeit ändern

### Für Administratoren:
- 👥 **User-Verwaltung** - Neue User erstellen und verwalten
- 🔄 **Passwort-Reset** - Passwörter aller User zurücksetzen
- 🗑️ **User löschen** - Nicht mehr benötigte Accounts entfernen

## 🚀 Schnellstart

### Voraussetzungen
- Python 3.9+
- Node.js 18+
- npm oder yarn

### Backend starten

\`\`\`bash
cd backend
pip install -r requirements.txt
python3 flask_server.py
\`\`\`

Server läuft auf: **http://localhost:8000**

### Frontend starten

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Frontend läuft auf: **http://localhost:5173**

## 📰 Scraper

Der Scraper liegt als Paket unter `backend/nzz_scraper/` und fährt einen echten
Chromium im **Mobilgerät-Profil** (`Pixel 7`), weil die mobilen NZZ-Seiten
einfacher strukturiert sind. Die Login-Session wird in `backend/.state/`
zwischengespeichert und nur bei Bedarf erneuert.

```bash
cd backend
python run_scraper.py                          # inkrementeller Lauf
python run_scraper.py --rescrape               # letzte 12h löschen und neu scrapen
python run_scraper.py --rescrape 24            # letzte 24h
python run_scraper.py --limit 3 --dry-run      # Probelauf ohne zu schreiben
python run_scraper.py --headed --log-level DEBUG   # Fehlersuche mit sichtbarem Browser
```

### NZZ Pro

NZZ hat zwei Abostufen. Deckt das Abo die **NZZ-Pro-Artikel** nicht ab, werden
sie übersprungen – und zwar schon anhand der Teaser-Markierung im Feed, also
ohne die Seite überhaupt zu laden.

Die Stufe wird beim ersten Lauf selbst ermittelt (ein Pro-Artikel als
Stichprobe) und in `backend/.state/nzz_entitlement.json` gemerkt; nach sieben
Tagen wird neu geprüft, damit ein Upgrade auffällt.

```bash
python run_scraper.py --pro-access no    # Pro fest ausschliessen (spart die Stichprobe)
python run_scraper.py --pro-access yes   # Pro-Abo vorhanden
python run_scraper.py --recheck-pro      # Stufe sofort neu ermitteln
```

Alternativ per `.env`: `NZZ_PRO_ACCESS=auto|yes|no`, `NZZ_PRO_RECHECK_DAYS=7`.

Übersprungene Pro-Artikel werden **nicht** getrackt – nach einem Upgrade sammelt
der nächste Lauf sie ein.

Exit-Codes: `0` ok · `1` zu viele Fehler · `2` Login/Konfiguration · `3` von NZZ
blockiert. `nzz-scraper-sync.sh` wertet sie aus und synchronisiert nur bei `0`.

Bei Problemen landen Screenshot, HTML und alle Sensorwerte unter
`backend/debug/<zeitstempel>-<anlass>/`. Die mobilen Selektoren lassen sich mit
`python -m nzz_scraper.tools.explore --url <url>` neu ermitteln.

### Automatischer Sync alle 30 Minuten (macOS LaunchAgent)

Auf macOS lässt sich `nzz-scraper-sync.sh` per **LaunchAgent** alle 30 Minuten
automatisch ausführen. Der Agent lädt bei jedem Login (überlebt Reboot); während
Sleep wird pausiert und ein verpasster Slot direkt nach dem Wake nachgeholt.
launchd startet pro Label maximal eine Instanz gleichzeitig – überlappende Läufe
sind damit ausgeschlossen.

Plist anlegen (Pfad anpassen falls das Repo woanders liegt):

```bash
cat > ~/Library/LaunchAgents/org.baettig.nzz-scraper-sync.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.baettig.nzz-scraper-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>/Users/&lt;you&gt;/Development/NZZApp/backend/nzz-scraper-sync.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/&lt;you&gt;/Development/NZZApp/backend</string>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/&lt;you&gt;/Development/NZZApp/backend/scraper_sync_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/&lt;you&gt;/Development/NZZApp/backend/scraper_sync_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
PLIST

plutil -lint ~/Library/LaunchAgents/org.baettig.nzz-scraper-sync.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.baettig.nzz-scraper-sync.plist
```

Status prüfen bzw. sofort einen Lauf triggern:

```bash
launchctl print gui/$(id -u)/org.baettig.nzz-scraper-sync | grep -E "state|next fire|last exit|run interval"
launchctl kickstart -k gui/$(id -u)/org.baettig.nzz-scraper-sync
```

Voraussetzungen: SSH-Key ohne Passphrase (bzw. `ssh-agent` aktiv) für
`baettig@baettig.org`, `backend/venv` eingerichtet, `.env` gefüllt.

Wieder deaktivieren:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/org.baettig.nzz-scraper-sync.plist
rm ~/Library/LaunchAgents/org.baettig.nzz-scraper-sync.plist
```

## 🔐 Standard-Login

\`\`\`
Email: reto@baettig.org
Passwort: 123
\`\`\`

⚠️ **Wichtig:** Ändere das Admin-Passwort nach dem ersten Login!

## 🧪 Tests

### Scraper (live gegen nzz.ch)

Fährt den echten Scraper im Mobilgerät-Profil: Cookie-Consent, Seitentyp-Erkennung,
Login von null, Login aus gespeicherter Session, Re-Login-Fallback, Feed,
Artikel-Extraktion, Paywall-Erkennung und die Kompatibilität der Artefakte mit
Flask und Frontend. Schreibt ausschliesslich in ein temporäres Verzeichnis;
`backend/articles/` und `backend/.state/` bleiben nachweislich unberührt.

```bash
backend/venv/bin/python tests/scraper_smoke_test.py
backend/venv/bin/python tests/scraper_smoke_test.py --headed
backend/venv/bin/python tests/scraper_smoke_test.py --only output,browser   # ohne Login
```

Ohne `NZZ_EMAIL`/`NZZ_PASSWORD` werden die Login-Abschnitte übersprungen (⊘).

### Frontend (End-to-End)

End-to-End Smoke-Test, der den kompletten Stack in einem echten Browser durchfährt
(Auth, ZIP-Download, Markdown-Parsing, Navigation, Datumswechsel, Markieren,
"Gelesene ausblenden", Admin-Panel, Reload). Der Test startet Backend und
Dev-Server selbst auf eigenen Ports (8011 / 5183) und legt eigene Test-Artikel an
— eine laufende Dev-Umgebung wird dadurch nicht gestört, und `users.json` sowie
`backend/articles/` bleiben unberührt.

```bash
backend/venv/bin/python tests/smoke_test.py            # headless
backend/venv/bin/python tests/smoke_test.py --headed   # mit sichtbarem Browser
backend/venv/bin/python tests/smoke_test.py --keep-logs
```

Exit-Code 0 = alle Checks grün. Voraussetzungen: `backend/venv` eingerichtet,
`frontend/node_modules` installiert und die Playwright-Chromium-Binary:

```bash
backend/venv/bin/python -m playwright install chromium
sudo apt install -y libasound2t64   # Systembibliothek für Chromium
```

Linting des Frontends:

```bash
cd frontend && npm run lint
```

## 📚 Dokumentation

- **[AUTH_README.md](backend/AUTH_README.md)** - Detaillierte Auth-Dokumentation
- **[nzz_scraper/MOBILE_SELECTORS.md](backend/nzz_scraper/MOBILE_SELECTORS.md)** - Wie die mobilen NZZ-Selektoren ermittelt wurden
- **[CHANGELOG.md](CHANGELOG.md)** - Alle Änderungen und Updates
- **[tests/smoke_test.py](tests/smoke_test.py)** - End-to-End Smoke-Test

## 🔒 Sicherheit

- Passwort-Hashing mit bcrypt
- JWT Token-Authentifizierung (24h)
- Geschützte API-Endpoints
- Admin-Permissions

---

**Version:** 2.1.0 | **Letzte Aktualisierung:** 20. Februar 2026
