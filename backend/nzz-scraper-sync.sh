#!/bin/bash
# NZZ Scraper - lokal ausführen und die Artefakte auf den Server kopieren.
set -uo pipefail

# Verzeichnis dieses Skripts, nicht ein geratener $HOME-Pfad.
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_USER="baettig"
REMOTE_HOST="baettig.org"
REMOTE_DIR="/var/www/nzzapp/backend/articles"
LOG_FILE="$LOCAL_DIR/scraper_log.txt"

cd "$LOCAL_DIR" || { echo "Verzeichnis $LOCAL_DIR nicht gefunden" >&2; exit 1; }

# shellcheck disable=SC1091
source venv/bin/activate

# Der Scraper rotiert scraper_log.txt selbst; auf der Konsole nur Warnungen,
# damit cron nur bei echten Problemen mailt.
python run_scraper.py --log-level WARNING
SCRAPER_EXIT=$?

case $SCRAPER_EXIT in
  0)
    rsync -avz "$LOCAL_DIR/articles/"*.zip "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" \
      && rsync -avz "$LOCAL_DIR/articles/scraped_articles.json" \
                    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" \
      && rsync -avz "$LOCAL_DIR/articles/"*/manifest.json \
                    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" 2>/dev/null
    echo "$(date -Is) sync ok" >> "$LOG_FILE"
    ;;
  2) echo "$(date -Is) Login-/Konfigurationsproblem – kein Sync" | tee -a "$LOG_FILE" >&2 ;;
  3) echo "$(date -Is) von NZZ blockiert – kein Sync, nächsten Lauf abwarten" | tee -a "$LOG_FILE" >&2 ;;
  *) echo "$(date -Is) Scraper fehlgeschlagen (Exit $SCRAPER_EXIT) – kein Sync" | tee -a "$LOG_FILE" >&2 ;;
esac

exit $SCRAPER_EXIT
