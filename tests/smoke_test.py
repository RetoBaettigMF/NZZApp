#!/usr/bin/env python3
"""
End-to-End Smoke-Test für den NZZ Reader.

Startet Backend und Vite-Dev-Server auf eigenen Ports (damit eine laufende
Dev-Umgebung nicht gestört wird), legt Test-Artikel an und fährt die App in
einem echten Browser durch die wichtigsten Abläufe:

  Auth · Artikel laden · Navigation · Datumswechsel · Markieren ·
  "Gelesene ausblenden" · Admin-Panel · Reload/Offline-Pfad

Es gibt bewusst keine Mocks: getestet wird der reale Stack inklusive
ZIP-Download, Markdown-Parsing und LocalStorage.

Aufruf (vom Repo-Root):

    backend/venv/bin/python tests/smoke_test.py
    backend/venv/bin/python tests/smoke_test.py --headed   # Browser sichtbar

Exit-Code 0 = alle Checks grün, 1 = mindestens ein Check rot.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / 'backend'
FRONTEND = REPO / 'frontend'
VENV_PY = BACKEND / 'venv' / 'bin' / 'python'

# Eigene Ports, damit ein parallel laufender Dev-Server unberührt bleibt
BACKEND_PORT = 8011
FRONTEND_PORT = 5183
JWT_SECRET = 'smoke-test-secret-not-for-production'

BASE_URL = f'http://localhost:{FRONTEND_PORT}'
API_URL = f'http://localhost:{BACKEND_PORT}'


# ---------------------------------------------------------------- Reporting

class Report:
    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, name, condition, detail=''):
        if condition:
            self.passed += 1
            print(f'  \033[32m✓\033[0m {name}' + (f' — {detail}' if detail else ''))
        else:
            self.failed.append(name)
            print(f'  \033[31m✗\033[0m {name}' + (f' — {detail}' if detail else ''))

    def equals(self, name, actual, expected):
        self.check(name, actual == expected, f'erwartet {expected!r}, erhalten {actual!r}')

    def summary(self):
        print()
        if self.failed:
            print(f'\033[31mFEHLGESCHLAGEN\033[0m: {len(self.failed)} von '
                  f'{self.passed + len(self.failed)} Checks')
            for f in self.failed:
                print(f'  - {f}')
            return 1
        print(f'\033[32mOK\033[0m: alle {self.passed} Checks grün')
        return 0


def section(title):
    print(f'\n\033[1m{title}\033[0m')


# ---------------------------------------------------------------- Fixtures

def seed_articles(articles_dir, days=((0, 3), (1, 2))):
    """Legt Test-ZIPs an. days = ((Tages-Offset, Artikelanzahl), ...)."""
    articles_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    created = {}
    for offset, count in days:
        day = today - datetime.timedelta(days=offset)
        with zipfile.ZipFile(articles_dir / f'{day.isoformat()}.zip', 'w') as z:
            for i in range(1, count + 1):
                z.writestr(f'artikel-{i}.md', (
                    f'# Testartikel {i} vom {day.isoformat()}\n\n'
                    f'**Datum:** {day.isoformat()}T08:0{i}:00\n'
                    f'**Kategorie:** Testkategorie\n'
                    f'**Zusammenfassung:** Kurze Testzusammenfassung {i}.\n\n'
                    f'[Original auf NZZ.ch öffnen](https://www.nzz.ch/test-{day.isoformat()}-{i})\n\n'
                    f'## Abschnitt eins\n\n'
                    f'Fliesstext des Testartikels {i} mit **bold** und *italic*.\n'
                ))
        created[day.isoformat()] = count
    return created


def make_token(is_admin=True, hours=1):
    import jwt
    return jwt.encode({
        'user_id': 'smoke-1',
        'email': 'smoke@test.local',
        'is_admin': is_admin,
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=hours),
    }, JWT_SECRET, algorithm='HS256')


# ---------------------------------------------------------------- Prozesse

def wait_for(url, timeout=60, label=''):
    """Pollt eine URL bis sie antwortet."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return True
        except urllib.error.HTTPError:
            return True          # antwortet, nur nicht mit 2xx → läuft
        except Exception as e:
            last = e
        time.sleep(0.3)
    raise RuntimeError(f'{label or url} nicht erreichbar nach {timeout}s (letzter Fehler: {last})')


def start_backend(articles_dir, log):
    env = {**os.environ,
           'OUTPUT_DIR': str(articles_dir),
           'JWT_SECRET_KEY': JWT_SECRET,
           'PORT': str(BACKEND_PORT),
           # Reloader aus: sonst überlebt ein Kindprozess das Teardown
           'FLASK_DEBUG': '0'}
    p = subprocess.Popen([str(VENV_PY), 'flask_server.py'], cwd=BACKEND, env=env,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    wait_for(f'{API_URL}/api/health', label='Backend')
    return p


def start_frontend(log):
    env = {**os.environ, 'VITE_API_TARGET': API_URL}
    p = subprocess.Popen(['npm', 'run', 'dev', '--', '--port', str(FRONTEND_PORT),
                          '--strictPort'],
                         cwd=FRONTEND, env=env,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    wait_for(BASE_URL, label='Vite-Dev-Server')
    return p


def stop(p):
    if p and p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)


# ---------------------------------------------------------------- API-Checks

def api_request(path, token=None):
    req = urllib.request.Request(API_URL + path)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def check_api(rep, token):
    section('API / Auth')
    rep.equals('/api/health ohne Token → 200', api_request('/api/health')[0], 200)
    rep.equals('/api/list ohne Token → 401', api_request('/api/list')[0], 401)
    rep.equals('/api/list mit ungültigem Token → 401',
               api_request('/api/list', 'kaputt.token.hier')[0], 401)

    status, body = api_request('/api/list', token)
    rep.equals('/api/list mit Token → 200', status, 200)
    dates = [a['date'] for a in (body or {}).get('archives', [])]
    rep.equals('/api/list liefert beide Test-Archive', len(dates), 2)

    status, body = api_request('/api/latest', token)
    rep.equals('/api/latest → 200', status, 200)
    rep.equals('/api/latest liefert das neueste Datum',
               (body or {}).get('date'), datetime.date.today().isoformat())

    rep.equals('/api/users als Nicht-Admin → 403',
               api_request('/api/users', make_token(is_admin=False))[0], 403)


# ---------------------------------------------------------------- UI-Checks

def check_ui(rep, token, headed):
    from playwright.sync_api import sync_playwright

    console_errors, page_errors, api_calls = [], [], Counter()
    today = datetime.date.today().isoformat()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={'width': 420, 'height': 900})
        page = ctx.new_page()
        page.on('console', lambda m: m.type == 'error' and console_errors.append(m.text))
        page.on('pageerror', lambda e: page_errors.append(str(e)))
        page.on('request', lambda r: '/api/' in r.url and api_calls.update(
            [re.sub(r'/api/download/.*', '/api/download/*', r.url.split(str(FRONTEND_PORT))[-1])]))

        # Als eingeloggt starten – der Login-Flow selbst braucht ein echtes
        # Passwort und wird oben auf API-Ebene geprüft.
        page.add_init_script(
            f"localStorage.setItem('nzz_auth_token', {json.dumps(token)});"
            f"localStorage.setItem('nzz_user', JSON.stringify("
            f"{{id:'smoke-1',email:'smoke@test.local',is_admin:true}}));")

        def counter():
            return page.locator('.article-count').first.inner_text()

        def title():
            return page.locator('.article-title, h2').first.inner_text().strip()

        def open_menu():
            """Öffnet das Hamburger-Menü, falls es nicht schon offen ist.
            Der Hamburger-Button toggelt – blindes Klicken würde ein offenes
            Menü wieder schliessen."""
            if page.locator('.dropdown-menu').count() == 0:
                page.locator('.hamburger-btn').click()
                page.wait_for_selector('.dropdown-menu', timeout=5000)

        section('Laden & Anzeige')
        page.goto(BASE_URL, wait_until='networkidle')
        page.wait_for_selector('.article-count', timeout=20000)
        page.wait_for_timeout(1500)

        rep.equals('Startet beim neuesten Tag mit 3 Artikeln', counter(), '1/3')
        rep.check('Neuester Artikel zuerst', title() == f'Testartikel 3 vom {today}', title())
        stored = json.loads(page.evaluate("localStorage.getItem('nzz_articles')") or '[]')
        rep.equals('Alle 5 Artikel im LocalStorage', len(stored), 5)
        rep.check('Markdown wurde zu HTML gerendert',
                  page.locator('.article-body strong, strong').count() > 0)
        rep.equals('DateNavigator sichtbar', page.locator('.date-navigator').count(), 1)

        section('Navigation')
        page.get_by_text('Weiter →').click(); page.wait_for_timeout(700)
        rep.equals('Weiter → 2/3', counter(), '2/3')
        page.get_by_text('Weiter →').click(); page.wait_for_timeout(700)
        rep.equals('Weiter → 3/3', counter(), '3/3')
        page.get_by_text('← Zurück').click(); page.wait_for_timeout(700)
        rep.equals('Zurück → 2/3', counter(), '2/3')
        page.get_by_text('🔝 Neuester Artikel').click(); page.wait_for_timeout(700)
        rep.equals('Neuester Artikel → 1/3', counter(), '1/3')

        section('Markieren')
        page.get_by_text('☆ Markieren').click(); page.wait_for_timeout(500)
        saved = json.loads(page.evaluate("localStorage.getItem('nzz_saved_articles')") or '[]')
        rep.equals('Ein Artikel markiert', len(saved), 1)

        section('Datumswechsel')
        page.locator('.date-navigator .header-icon-btn').first.click()
        page.wait_for_timeout(1800)
        rep.equals('Älterer Tag zeigt 2 Artikel', counter(), '1/2')

        section('Gelesene ausblenden')
        open_menu()
        page.locator('.menu-toggle').click(); page.wait_for_timeout(1200)
        rep.equals('Einstellung persistiert',
                   page.evaluate("localStorage.getItem('nzz_hide_read_articles')"), 'true')
        read = json.loads(page.evaluate("localStorage.getItem('nzz_read_articles')") or '[]')
        rep.check('Gelesene Artikel wurden erfasst', len(read) >= 3, f'{len(read)} gelesen')
        rep.check('Anzeige bleibt gültig (currentIndex-Clamp)',
                  re.fullmatch(r'\d+/\d+', counter()) is not None, counter())

        section('Admin-Panel')
        open_menu()
        page.get_by_text('User-Verwaltung').first.click(); page.wait_for_timeout(1800)
        rep.check('Panel geöffnet', page.locator('.admin-panel').count() > 0)
        rep.check('User-Liste ohne Fehlermeldung geladen',
                  '@' in page.inner_text('body') and
                  'Fehler beim Laden der User' not in page.inner_text('body'))
        page.keyboard.press('Escape'); page.wait_for_timeout(400)

        section('Reload (LocalStorage-Pfad)')
        api_calls.clear()
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.article-count', timeout=20000)
        page.wait_for_timeout(2000)
        rep.check('Artikel nach Reload wieder da',
                  re.fullmatch(r'\d+/\d+', counter()) is not None, counter())
        # StrictMode ruft Mount-Effects doppelt auf → 2 erwartet, >4 heisst Schleife
        for endpoint, limit in (('/api/latest', 4), ('/api/list', 4), ('/api/download/*', 8)):
            rep.check(f'Keine Nachlade-Schleife auf {endpoint}',
                      api_calls[endpoint] <= limit,
                      f'{api_calls[endpoint]}x (max {limit})')

        section('Konsole')
        rep.check('Keine console.error', not console_errors, '; '.join(console_errors[:3]))
        rep.check('Keine unbehandelten Exceptions', not page_errors, '; '.join(page_errors[:3]))

        browser.close()


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--headed', action='store_true', help='Browser sichtbar starten')
    ap.add_argument('--keep-logs', action='store_true',
                    help='Server-Logs nicht löschen (Pfade werden ausgegeben)')
    args = ap.parse_args()

    if not VENV_PY.exists():
        sys.exit(f'venv fehlt: {VENV_PY}\n'
                 'Setup: cd backend && python3 -m venv venv && '
                 './venv/bin/pip install -r requirements.txt')
    if not (FRONTEND / 'node_modules').exists():
        sys.exit('node_modules fehlen. Setup: cd frontend && npm install')

    tmp = Path(tempfile.mkdtemp(prefix='nzz-smoke-'))
    articles_dir = tmp / 'articles'
    be_log_path, fe_log_path = tmp / 'backend.log', tmp / 'frontend.log'
    backend = frontend = None
    rep = Report()

    print(f'\033[1mNZZ Reader – Smoke-Test\033[0m')
    print(f'  Arbeitsverzeichnis: {tmp}')

    try:
        seeded = seed_articles(articles_dir)
        print(f'  Test-Artikel: {seeded}')

        with open(be_log_path, 'w') as be_log, open(fe_log_path, 'w') as fe_log:
            print(f'  Backend startet auf {API_URL} ...')
            backend = start_backend(articles_dir, be_log)
            print(f'  Frontend startet auf {BASE_URL} ...')
            frontend = start_frontend(fe_log)

            token = make_token()
            check_api(rep, token)
            check_ui(rep, token, args.headed)

    except Exception as e:
        print(f'\n\033[31mAbbruch:\033[0m {type(e).__name__}: {e}')
        for name, path in (('Backend', be_log_path), ('Frontend', fe_log_path)):
            if path.exists():
                tail = path.read_text(errors='replace').splitlines()[-15:]
                if tail:
                    print(f'\n--- {name}-Log (letzte Zeilen) ---')
                    print('\n'.join(tail))
        rep.failed.append(f'Ausführung abgebrochen: {e}')
    finally:
        stop(frontend)
        stop(backend)
        if args.keep_logs:
            print(f'\nLogs: {be_log_path}  {fe_log_path}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    sys.exit(rep.summary())


if __name__ == '__main__':
    main()
