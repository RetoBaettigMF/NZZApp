#!/bin/bash
# NZZ Scraper - Lokal ausführen und auf Server kopieren

LOCAL_DIR="$HOME/Development/NZZApp/backend"
REMOTE_USER="baettig"
REMOTE_HOST="baettig.org"
REMOTE_DIR="/var/www/nzzapp/backend/articles"
LOG_FILE="$LOCAL_DIR/sraper_log.txt"

# Log-Verzeichnis erstellen
# mkdir -p "$HOME/.local/log"

echo "==========================================" >> "$LOG_FILE"
echo "NZZ Scraper Sync - $(date)" >> "$LOG_FILE"
echo "==========================================" >> "$LOG_FILE"

# Scraper ausführen
cd "$LOCAL_DIR"
source venv/bin/activate
python scraper.py >> "$LOG_FILE" 2>&1
SCRAPER_EXIT=$?

if [ $SCRAPER_EXIT -eq 0 ]; then
    echo "✓ Scraper erfolgreich" >> "$LOG_FILE"
    
    # Neue .zip-Dateien auf Server kopieren
    rsync -avz --progress "$LOCAL_DIR/articles/"*.zip "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" >> "$LOG_FILE" 2>&1
    RSYNC_EXIT=$?
    
    if [ $RSYNC_EXIT -eq 0 ]; then
        echo "✓ ZIP-Dateien auf Server kopiert" >> "$LOG_FILE"
    else
        echo "✗ Fehler beim Kopieren (Exit: $RSYNC_EXIT)" >> "$LOG_FILE"
    fi
    
    # Auch scraped_articles.json und Manifeste synchronisieren
    rsync -avz "$LOCAL_DIR/articles/scraped_articles.json" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" >> "$LOG_FILE" 2>&1
    rsync -avz "$LOCAL_DIR/articles/"*/manifest.json "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" 2>/dev/null || true
    
else
    echo "✗ Scraper fehlgeschlagen (Exit: $SCRAPER_EXIT)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
