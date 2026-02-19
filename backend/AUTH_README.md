# NZZ Reader - Authentication System

## Übersicht

Das NZZ Reader System verfügt jetzt über ein vollständiges Login-System mit Admin-Funktionen.

## Standard Admin-Zugang

- **Email:** reto@baettig.org
- **Passwort:** 123

## Backend starten

```bash
cd backend
python3 flask_server.py
```

Der Server läuft dann auf http://localhost:8000

## Frontend starten

```bash
cd frontend
npm run dev
```

Das Frontend läuft dann auf http://localhost:5173

## Funktionen

### Für alle User:
- Login/Logout
- Eigenes Passwort ändern
- Artikel lesen und verwalten

### Für Admin (reto@baettig.org):
- Neue User erstellen
- User löschen
- Passwörter aller User zurücksetzen

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login mit Email/Passwort
- `GET /api/auth/me` - Aktueller User (authentifiziert)
- `POST /api/auth/change-password` - Passwort ändern (authentifiziert)

### User Management (Admin only)
- `GET /api/users` - Alle User auflisten
- `POST /api/users` - Neuen User erstellen
- `DELETE /api/users/:id` - User löschen
- `POST /api/users/:id/reset-password` - Passwort zurücksetzen

### Articles (authentifiziert)
- `GET /api/latest` - Neuestes Archiv
- `GET /api/list` - Alle Archive
- `GET /api/download/:date` - ZIP herunterladen

## Sicherheit

- Passwörter werden mit bcrypt gehasht
- JWT Tokens für Authentication (24h Gültigkeit)
- Admin-only Endpoints geschützt
- CORS aktiviert für Frontend-Zugriff

## User-Daten

User werden in `backend/users.json` gespeichert.

**WICHTIG:** Diese Datei nicht ins Git committen wenn Produktions-Passwörter enthalten sind!
