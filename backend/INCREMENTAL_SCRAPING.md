# Inkrementelles Scraping

> **Stand August 2026:** Der Scraper liegt als Paket unter `backend/nzz_scraper/`.
> Die frühere Einzeldatei `backend/scraper.py` gibt es nicht mehr, und der
> Aufruf lautet `python run_scraper.py` statt `python scraper.py`.
> Das hier beschriebene Tracking-Format ist **unverändert** – es wird von
> `migrate_tracking.py`, `flask_server.py` und dem Frontend gelesen.
> Neu ist: Artikel hinter der Paywall werden **nicht** gespeichert und **nicht**
> getrackt, damit sie beim nächsten Lauf erneut versucht werden.
>
> Architektur und Sensoren: `backend/nzz_scraper/MOBILE_SELECTORS.md` und README.

## Was wurde implementiert?

Das NZZ Scraper System wurde um **inkrementelles Scraping mit Artikel-Tracking** erweitert. Der Scraper kann jetzt mehrmals täglich ausgeführt werden und scrapt nur neue, noch nicht heruntergeladene Artikel.

## Hauptmerkmale

### 1. Zentrale Tracking-Liste
**Datei:** `articles/scraped_articles.json`

Format:
```json
{
  "articles": [
    {
      "url": "https://www.nzz.ch/...",
      "scraped_date": "2026-02-17",
      "filename": "2026-02-17/kategorie/Artikel_Titel.md",
      "title": "Artikel Titel"
    }
  ],
  "last_updated": "2026-02-17T18:02:48.395846"
}
```

### 2. Neue Scraper-Methoden

**In `nzz_scraper/pipeline/tracking.py` (`TrackingStore`):**
- `load_tracked_articles()` - Lädt persistente Tracking-Datei
- `save_tracked_articles()` - Speichert aktualisierte Tracking-Datei
- `is_article_scraped()` - Prüft ob URL bereits gescrapt wurde
- `add_to_tracking()` - Fügt gescrapten Artikel zum Tracking hinzu
- `update_manifest()` - Aktualisiert Manifest mit allen Artikeln im Ordner

### 3. Überarbeitete `run()` Logik

**Workflow:**
1. Tracking-Datei laden
2. Artikel-Links von Homepage holen
3. **Nur neue Links filtern** (nicht im Tracking)
4. Nur neue Artikel scrapen
5. Jeder Artikel wird sofort zum Tracking hinzugefügt
6. Tracking-Datei speichern
7. ZIP des heutigen Tages neu erstellen (überschreibt altes)
8. Manifest aktualisieren

### 4. Migration für bestehende Artikel

**Script:** `migrate_tracking.py`

Durchsucht alle bestehenden Artikel-Verzeichnisse und initialisiert die Tracking-Datei mit allen URLs, die bereits heruntergeladen wurden.

## Test-Ergebnisse

### Migration
```
✓ 43 Artikel aus bestehenden Ordnern zum Tracking hinzugefügt
  - 2026-02-14: 0 Artikel (alte Formatierung)
  - 2026-02-16: 28 Artikel
  - 2026-02-17: 15 Artikel (4 Duplikate erkannt)
```

### Erster Scraper-Run
```
ℹ 43 Artikel bereits gescrapt
✓ 19 Links gefunden auf Homepage
✓ 12 NEUE Artikel gescrapt (7 waren bereits bekannt)
✓ Tracking aktualisiert: 55 Artikel total
```

### Zweiter Scraper-Run (2 Minuten später)
```
ℹ 55 Artikel bereits gescrapt
✓ 19 Links gefunden auf Homepage
✓ 1 NEUER Artikel gescrapt (18 waren bereits bekannt)
✓ Tracking aktualisiert: 56 Artikel total
```

**Beweis:** Ein neuer Artikel erschien zwischen den Runs, und der Scraper erkannte ihn korrekt als neu!

## Vorteile

### ✅ Effizienz
- Nur neue Artikel werden gescrapt
- Spart AI-Bereinigungskosten (OpenRouter)
- Spart Bandbreite und Zeit

### ✅ Inkrementelle Updates
- Scraper kann stündlich laufen (z.B. per Cronjob)
- Holt kontinuierlich neue Artikel über den Tag verteilt
- Keine Duplikate mehr

### ✅ State-Management
- Persistente Tracking-Datei als Single Source of Truth
- Nachvollziehbar: Wann wurde welcher Artikel gescrapt?
- Ermöglicht Analysen und Statistiken

### ✅ Tages-Organisation
- Artikel werden weiterhin nach Datum organisiert
- Heutiges ZIP wird bei jedem Run aktualisiert
- Alte ZIPs bleiben final und unverändert

## Verzeichnisstruktur

```
articles/
├── scraped_articles.json          # ZENTRALE TRACKING-LISTE
├── 2026-02-14/
│   ├── kategorie1/*.md
│   ├── kategorie2/*.md
│   └── manifest.json
├── 2026-02-14.zip                 # FINAL (wird nicht mehr geändert)
├── 2026-02-17/
│   ├── wirtschaft/*.md
│   ├── sport/*.md
│   ├── lokal/*.md
│   ├── welt/*.md
│   └── manifest.json
└── 2026-02-17.zip                 # AKTUELL (wird bei jedem Run überschrieben)
```

## Verwendung

### Normaler Scraper-Run
```bash
cd /home/reto/Development/NZZApp/backend
source venv/bin/activate
python run_scraper.py
```

**Ausgabe:**
```
ℹ 56 Artikel bereits gescrapt
ℹ 19 Links gefunden, 0 sind NEU
✓ Keine neuen Artikel zum Scrapen
```

### Migration bestehender Artikel
```bash
python migrate_tracking.py
```

**Nur einmal ausführen!** Initialisiert Tracking-Datei aus bestehenden Artikeln.

## Cronjob-Setup

Um den Scraper mehrmals täglich automatisch laufen zu lassen:

```bash
crontab -e
```

Beispiel: Alle 2 Stunden scrapen
```cron
0 */2 * * * cd /home/reto/Development/NZZApp/backend && source venv/bin/activate && python run_scraper.py >> /tmp/nzz_scraper.log 2>&1
```

## Monitoring

### Tracking-Status prüfen
```bash
cat articles/scraped_articles.json | jq '{ total: (.articles | length), last_updated: .last_updated }'
```

### Heutiges Manifest prüfen
```bash
cat articles/$(date +%Y-%m-%d)/manifest.json | jq '.'
```

### Artikel-Count pro Tag
```bash
for dir in articles/2026-*; do
  if [ -d "$dir" ]; then
    count=$(find "$dir" -name "*.md" | wc -l)
    echo "$(basename $dir): $count Artikel"
  fi
done
```

## Technische Details

### Duplikat-Erkennung
- Basiert auf **URL-Matching** (nicht Titel oder Inhalt)
- URLs werden in einem Set gespeichert für O(1) Lookup
- Sehr schnell auch bei tausenden Artikeln

### Manifest-Update
- Zählt **alle** .md Dateien im Tages-Ordner
- Nicht nur neu gescrapte Artikel
- Reflektiert den vollständigen Ordnerinhalt

### ZIP-Handling
- `zipfile.ZipFile(..., 'w', ...)` überschreibt automatisch
- Enthält immer den aktuellen Stand des Tages-Ordners
- Alte ZIPs werden nicht angefasst

### Robustheit
- Tracking-Datei wird nach jedem Artikel-Scraping aktualisiert
- Bei Abbruch: Bereits gescrapte Artikel sind im Tracking
- Nächster Run überspringt sie automatisch

## Potenzielle Erweiterungen

### 1. Artikel-Alterung
```python
# Lösche Tracking-Einträge älter als 90 Tage
cutoff_date = datetime.now() - timedelta(days=90)
tracking['articles'] = [
    a for a in tracking['articles']
    if datetime.fromisoformat(a['scraped_date']) > cutoff_date
]
```

### 2. Statistiken
```python
# Artikel pro Kategorie (gesamt)
from collections import Counter
stats = Counter([a['filename'].split('/')[1] for a in tracking['articles']])
```

### 3. Re-Scraping
```python
# Artikel älter als X Tage neu scrapen (für Updates)
def should_rescrape(article, days=30):
    age = datetime.now() - datetime.fromisoformat(article['scraped_date'])
    return age.days > days
```

## Zusammenfassung

Das inkrementelle Scraping-System ist **vollständig implementiert und getestet**. Es funktioniert zuverlässig und erfüllt alle Anforderungen:

- ✅ Zentrale Tracking-Liste
- ✅ Nur neue Artikel scrapen
- ✅ Tages-Verzeichnisse beibehalten
- ✅ Heutiges ZIP überschreiben
- ✅ Alte ZIPs unverändert

**Status:** Production-ready! 🚀
