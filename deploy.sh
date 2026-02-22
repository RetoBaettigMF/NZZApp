#!/bin/bash
# =============================================================================
# NZZ App – Deployment Script
# Holt die neueste Version von GitHub, baut das Frontend und deployt auf den
# Server baettig.org.
#
# Voraussetzung: Lokaler Stand ist committed und auf GitHub gepusht.
# Verwendung: ./deploy.sh
# =============================================================================

set -e  # Abbrechen bei Fehler

# --- Konfiguration ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$REPO_DIR/frontend"
BACKEND_DIR="$REPO_DIR/backend"

REMOTE_USER="baettig"
REMOTE_HOST="baettig.org"
REMOTE_WEB_ROOT="/var/www/nzzapp"
REMOTE_FRONTEND_DIR="$REMOTE_WEB_ROOT/frontend/dist"
REMOTE_BACKEND_DIR="$REMOTE_WEB_ROOT/backend"

# Name des systemd-Services für das Backend (leer lassen, falls keiner existiert)
BACKEND_SERVICE="nzzapp-backend"

# Farben für die Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()  { echo -e "${BLUE}>>>$NC $1"; }
ok()   { echo -e "${GREEN}✓$NC $1"; }
warn() { echo -e "${YELLOW}⚠$NC $1"; }
err()  { echo -e "${RED}✗$NC $1"; }

echo ""
echo "======================================================"
echo "  NZZ App – Deployment"
echo "  $(date '+%d.%m.%Y %H:%M:%S')"
echo "======================================================"
echo ""

# --- 1. Neueste Version von GitHub holen ---
log "Neueste Version von GitHub holen..."
cd "$REPO_DIR"
git pull origin master
ok "Git pull abgeschlossen (Branch: $(git rev-parse --abbrev-ref HEAD), Commit: $(git rev-parse --short HEAD))"
echo ""

# --- 2. Frontend bauen ---
log "Frontend-Abhängigkeiten installieren..."
cd "$FRONTEND_DIR"
npm install --silent
ok "npm install abgeschlossen"

log "Frontend bauen (npm run build)..."
npm run build
ok "Frontend-Build abgeschlossen → dist/"
echo ""

# --- 3. Frontend auf Server deployen ---
log "Frontend auf Server deployen (rsync)..."
rsync -rltvz --delete \
    --no-group --omit-dir-times \
    --exclude='.htaccess' \
    "$FRONTEND_DIR/dist/" \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_FRONTEND_DIR/"
ok "Frontend deployed nach $REMOTE_HOST:$REMOTE_FRONTEND_DIR/"
echo ""

# --- 4. Backend-Dateien auf Server deployen ---
log "Backend-Dateien auf Server deployen (rsync)..."
rsync -rltvz \
    --no-group --omit-dir-times \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='articles/' \
    --exclude='*.png' \
    --exclude='*_log.txt' \
    --exclude='*.log' \
    "$BACKEND_DIR/" \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BACKEND_DIR/"
ok "Backend deployed nach $REMOTE_HOST:$REMOTE_BACKEND_DIR/"
echo ""

# --- 5. Python-Abhängigkeiten auf Server aktualisieren ---
log "Python-Abhängigkeiten auf Server aktualisieren..."
ssh "$REMOTE_USER@$REMOTE_HOST" "
    cd '$REMOTE_BACKEND_DIR'
    if [ -d venv ]; then
        venv/bin/pip install -r requirements.txt -q && echo 'pip install OK'
    else
        echo 'Kein venv gefunden – Dependencies übersprungen'
    fi
"
ok "Python-Abhängigkeiten aktualisiert"
echo ""

# --- 6. Backend-Service neu laden (Gunicorn SIGHUP) ---
log "Backend neu laden..."
GUNICORN_PID=$(ssh "$REMOTE_USER@$REMOTE_HOST" "pgrep -f 'gunicorn.*flask_server' | head -1" 2>/dev/null || true)
if [ -n "$GUNICORN_PID" ]; then
    ssh "$REMOTE_USER@$REMOTE_HOST" "kill -HUP '$GUNICORN_PID'" 2>/dev/null || true
    sleep 1
    if ssh "$REMOTE_USER@$REMOTE_HOST" "systemctl is-active --quiet '$BACKEND_SERVICE'" 2>/dev/null; then
        ok "Gunicorn (PID $GUNICORN_PID) per SIGHUP neu geladen"
    else
        warn "SIGHUP fehlgeschlagen. Bitte manuell neustarten: systemctl restart $BACKEND_SERVICE"
    fi
else
    warn "Gunicorn läuft nicht. Einmaliger Start durch root nötig:"
    warn "  → systemctl start $BACKEND_SERVICE"
fi
echo ""

echo "======================================================"
echo -e "  ${GREEN}Deployment erfolgreich abgeschlossen!${NC}"
echo "  URL: https://baettig.org"
echo "======================================================"
echo ""
