# NZZ Reader App

Eine Progressive Web App (PWA) zum Lesen von NZZ Artikeln mit Offline-Support.

**Repository:** https://github.com/RetoBaettigMF/NZZApp

## Features

### Backend
- 🤖 Automatisches Scraping täglich um 06:00 Uhr
- 📚 Artikel als Markdown gespeichert (kategorisiert)
- 📦 Automatische ZIP-Archivierung
- 🗂️ Kategorien: Sport, Wirtschaft, Wissenschaft, Lokal, Welt
- 🔐 Login mit NZZ Account

### Frontend (PWA)
- 📱 Installierbar auf Smartphone/Desktop
- 💾 Offline-Support mit LocalStorage
- 🏷️ Kategorie-Filter
- 👆 Swipe-Navigation (Touch & Tastatur)
- ⭐ Artikel markieren zum Behalten
- 🗑️ Nicht markierte Artikel automatisch löschen

## Setup

### 1. Repository klonen
```bash
git clone https://github.com/RetoBaettigMF/NZZApp.git
cd NZZApp
```

### 2. Backend einrichten
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Erstmalige Konfiguration (fragt nach Passwort)
python init_config.py
```

### 3. Frontend einrichten
```bash
cd frontend
npm install
npm run build
```

## Verwendung

### Backend starten (Scheduler)
```bash
cd backend
source venv/bin/activate
python scheduler.py
```

Für sofortigen Testlauf:
```bash
python scheduler.py --run-now
```

### API Server starten (für Frontend)
```bash
cd backend
source venv/bin/activate
python api_server.py
```

Server läuft auf http://localhost:8000

### Frontend entwickeln
```bash
cd frontend
npm run dev
```

Dev-Server läuft auf http://localhost:5173

### Frontend bauen
```bash
cd frontend
npm run build
```

Die fertige PWA liegt im `dist/` Ordner.

## API Endpoints

- `GET /api/latest` - Informationen zum neuesten Archiv
- `GET /api/list` - Liste aller verfügbaren Archive
- `GET /api/download/YYYY-MM-DD` - ZIP-Archiv herunterladen

## Projektstruktur

```
NZZApp/
├── backend/
│   ├── scraper.py          # Haupt-Scraper
│   ├── scheduler.py        # Täglicher Scheduler
│   ├── api_server.py       # HTTP API
│   ├── init_config.py      # Erstkonfiguration
│   ├── create_icons.py     # Icon-Generator
│   └── articles/           # Gespeicherte Artikel
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── ArticleReader.jsx
│   │       ├── CategorySelector.jsx
│   │       └── ZipLoader.jsx
│   └── dist/               # Build-Output
└── README.md
```

## Tastatur-Navigation

- `→` oder `Leertaste` - Nächster Artikel
- `←` - Vorheriger Artikel
- `*` - Artikel markieren/demarkieren

## Touch-Gesten

- Swipe nach links - Nächster Artikel
- Swipe nach rechts - Vorheriger Artikel

## Wichtige Hinweise

- Das NZZ-Passwort wird in `backend/.env` gespeichert
- Artikel werden in `backend/articles/` als Markdown gespeichert
- ZIP-Archive werden automatisch erstellt
- Markierte Artikel werden nicht gelöscht

## Technologien

- **Backend:** Python, requests, BeautifulSoup, schedule
- **Frontend:** React, Vite, JSZip, PWA
- **Storage:** LocalStorage (Frontend), Filesystem (Backend)

## Lizenz

Privates Projekt für persönlichen Gebrauch.
