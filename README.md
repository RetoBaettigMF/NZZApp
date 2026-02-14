# NZZ Reader App

Eine PWA zum Lesen von NZZ Artikeln mit Offline-Support.

## Projektstruktur

- `/backend` - Python Service zum Scrapen und Archivieren von Artikeln
- `/frontend` - React PWA zum Lesen der Artikel

## Setup

### Backend
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python init_config.py  # Fragt nach NZZ Passwort
```

### Frontend
```bash
cd frontend
npm install
npm run build
```

## Automatisierung

Das Backend läuft täglich um 06:00 Uhr und scraped die neuesten Artikel.
