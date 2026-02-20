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

## 📚 Dokumentation

- **[AUTH_README.md](backend/AUTH_README.md)** - Detaillierte Auth-Dokumentation
- **[CHANGELOG.md](CHANGELOG.md)** - Alle Änderungen und Updates

## 🔒 Sicherheit

- Passwort-Hashing mit bcrypt
- JWT Token-Authentifizierung (24h)
- Geschützte API-Endpoints
- Admin-Permissions

---

**Version:** 2.1.0 | **Letzte Aktualisierung:** 20. Februar 2026
