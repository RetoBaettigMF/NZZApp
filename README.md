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

## 🔐 Standard-Login

\`\`\`
Email: reto@baettig.org
Passwort: 123
\`\`\`

⚠️ **Wichtig:** Ändere das Admin-Passwort nach dem ersten Login!

## 🧪 Tests

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
- **[CHANGELOG.md](CHANGELOG.md)** - Alle Änderungen und Updates
- **[tests/smoke_test.py](tests/smoke_test.py)** - End-to-End Smoke-Test

## 🔒 Sicherheit

- Passwort-Hashing mit bcrypt
- JWT Token-Authentifizierung (24h)
- Geschützte API-Endpoints
- Admin-Permissions

---

**Version:** 2.1.0 | **Letzte Aktualisierung:** 20. Februar 2026
