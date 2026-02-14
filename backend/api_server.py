#!/usr/bin/env python3
"""
Einfacher HTTP Server für das Frontend.
Serviert die ZIP-Archive und erlaubt CORS für die PWA.
"""
import os
import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

ARTICLES_DIR = Path(os.getenv('OUTPUT_DIR', './articles'))

class APIHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # CORS Headers für PWA
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        # API Endpoints
        if parsed.path == '/api/latest':
            self.serve_latest()
        elif parsed.path == '/api/list':
            self.serve_list()
        elif parsed.path.startswith('/api/download/'):
            date = parsed.path.split('/')[-1]
            self.serve_zip(date)
        else:
            super().do_GET()
    
    def serve_latest(self):
        """Gibt das neueste verfügbare Datum zurück."""
        try:
            # Alle ZIP-Dateien finden
            zips = sorted(ARTICLES_DIR.glob('*.zip'), reverse=True)
            
            if not zips:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'No archives found'}).encode())
                return
            
            latest = zips[0]
            date = latest.stem
            
            # Manifest laden falls vorhanden
            manifest_path = ARTICLES_DIR / date / 'manifest.json'
            manifest = {}
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            
            response = {
                'date': date,
                'download_url': f'/api/download/{date}',
                'manifest': manifest
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def serve_list(self):
        """Gibt eine Liste aller verfügbaren Archive zurück."""
        try:
            zips = sorted(ARTICLES_DIR.glob('*.zip'), reverse=True)
            archives = []
            
            for zip_file in zips:
                date = zip_file.stem
                manifest_path = ARTICLES_DIR / date / 'manifest.json'
                manifest = {}
                if manifest_path.exists():
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                
                archives.append({
                    'date': date,
                    'download_url': f'/api/download/{date}',
                    'manifest': manifest
                })
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'archives': archives}).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def serve_zip(self, date):
        """Serviert eine ZIP-Datei."""
        try:
            zip_path = ARTICLES_DIR / f"{date}.zip"
            
            if not zip_path.exists():
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Archive not found'}).encode())
                return
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', f'attachment; filename="{date}.zip"')
            self.send_header('Content-Length', str(zip_path.stat().st_size))
            self.end_headers()
            
            with open(zip_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

def run_server(port=8000):
    """Startet den API Server."""
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"✓ API Server läuft auf http://localhost:{port}")
    print(f"  - /api/latest    - Neuestes Archiv")
    print(f"  - /api/list      - Alle Archive")
    print(f"  - /api/download/YYYY-MM-DD - ZIP herunterladen")
    print("\nDrücke Ctrl+C zum Beenden")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server beendet")

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
