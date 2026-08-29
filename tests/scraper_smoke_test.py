#!/usr/bin/env python3
"""Live-Smoke-Test für den NZZ-Scraper.

Fährt den echten Scraper gegen www.nzz.ch: Mobilgerät-Profil, Cookie-Consent,
Seitentyp-Erkennung, Login von null, Login aus der gespeicherten Session,
Re-Login-Fallback, Feed, Artikel-Extraktion, Paywall-Erkennung sowie die
Kompatibilität der erzeugten Artefakte mit Flask und dem Frontend.

Es wird ausschliesslich in ein temporäres Verzeichnis geschrieben;
backend/articles/ und backend/.state/ bleiben nachweislich unberührt.

Aufruf (vom Repo-Root):

    backend/venv/bin/python tests/scraper_smoke_test.py
    backend/venv/bin/python tests/scraper_smoke_test.py --headed
    backend/venv/bin/python tests/scraper_smoke_test.py --only output,tracking
    backend/venv/bin/python tests/scraper_smoke_test.py --with-ai --keep-artifacts

Ohne NZZ_EMAIL/NZZ_PASSWORD werden die Login-Abschnitte übersprungen (⊘) und
zählen weder als grün noch als rot. Exit-Code 0 = alle Checks grün.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / 'backend'
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_test import Report  # noqa: E402  – gleiche Ausgabeoptik wie der Frontend-Test

from nzz_scraper.browser import BrowserSession                       # noqa: E402
from nzz_scraper.config import ScraperConfig                         # noqa: E402
from nzz_scraper.debug import DebugArtifacts                         # noqa: E402
from nzz_scraper.extraction.markdown import html_fragment_to_markdown  # noqa: E402
from nzz_scraper.logging_setup import setup_logging                  # noqa: E402
from nzz_scraper.models import Article, PageType                     # noqa: E402
from nzz_scraper.pages.article import ArticlePage                    # noqa: E402
from nzz_scraper.pages.base import PageContext                       # noqa: E402
from nzz_scraper.pages.consent import CookieConsentOverlay           # noqa: E402
from nzz_scraper.pages.feed import LatestArticlesPage                # noqa: E402
from nzz_scraper.pages.home import HomePage                          # noqa: E402
from nzz_scraper.pipeline.auth_manager import AuthManager            # noqa: E402
from nzz_scraper.pipeline.output import ArticleWriter, create_zip, update_manifest  # noqa: E402
from nzz_scraper.pipeline.runner import ScraperRun                   # noqa: E402
from nzz_scraper.sensors import (BlockingSensor, ContentQualitySensor,  # noqa: E402
                                 PageTypeSensor, PaywallSensor)

ARTICLE_URL_RE = re.compile(r'^https://www\.nzz\.ch/[\w-]+/[\w-]+\.\d+$')

SECTIONS = ('browser', 'consent', 'pagetype', 'login', 'session', 'relogin',
            'feed', 'article', 'paywall', 'output', 'tracking', 'debug', 'isolation')


# ------------------------------------------------------------------ Gerüst

class SkipAwareReport(Report):
    """Report des Frontend-Smoke-Tests plus ein neutrales 'übersprungen'."""

    def __init__(self):
        super().__init__()
        self.skipped = []

    def skip(self, name, reason):
        self.skipped.append((name, reason))
        print(f'  \033[33m⊘\033[0m {name} — {reason}')

    def summary(self):
        code = super().summary()
        if self.skipped:
            print(f'\033[33m{len(self.skipped)} Checks übersprungen\033[0m')
            for name, reason in self.skipped:
                print(f'  - {name}: {reason}')
        return code


def section(title):
    print(f'\n\033[1m{title}\033[0m')


def make_ctx(cfg):
    debug = DebugArtifacts(cfg.debug_dir)
    return PageContext(cfg=cfg, debug=debug, page_type_sensor=PageTypeSensor()), debug


def snapshot(path: Path):
    """Dateiliste + mtimes eines Verzeichnisses, für den Unberührt-Nachweis."""
    if not path.exists():
        return None
    return {str(p.relative_to(path)): p.stat().st_mtime
            for p in sorted(path.rglob('*')) if p.is_file()}


# ------------------------------------------------------------------ Checks

def check_output_compat(rep, cfg):
    """Ohne Netz: erzeugte Artefakte gegen die Frontend-Regexes prüfen."""
    section('Output-Kompatibilität (ohne Netz)')
    day = cfg.output_dir / '2026-01-02'
    art = Article(title='Test: Ärger & Zürich!', url='https://www.nzz.ch/wirtschaft/x-ld.42',
                  date='2026-01-02T08:30:00', category='wirtschaft',
                  content='Absatz eins.\n\nAbsatz zwei.', summary='Kurz.\nMit Umbruch.')
    path = ArticleWriter(cfg.output_dir).write(art, day)
    update_manifest(day)
    zip_path = create_zip(day)

    parsed = parse_like_frontend(path.read_text(encoding='utf-8'))
    rep.equals('Titel überlebt den Rundlauf', parsed['title'], art.title)
    rep.equals('Datum überlebt den Rundlauf', parsed['date'], art.date)
    rep.equals('Kategorie überlebt den Rundlauf', parsed['category'], art.category)
    rep.equals('URL überlebt den Rundlauf', parsed['url'], art.url)
    rep.check('Zusammenfassung auf einer Zeile', parsed['summary'] == 'Kurz. Mit Umbruch.',
              repr(parsed['summary']))
    rep.check('Body nach dem --- Trenner', 'Absatz zwei.' in parsed['body'])

    manifest = json.loads((day / 'manifest.json').read_text())
    rep.equals('manifest.json hat exakt die drei Keys',
               sorted(manifest), ['categories', 'date', 'total_articles'])
    rep.equals('manifest zählt den Artikel', manifest['total_articles'], 1)

    names = zipfile.ZipFile(zip_path).namelist()
    rep.check('ZIP-Pfade sind <datum>/<kategorie>/<datei>.md',
              '2026-01-02/wirtschaft/Test_Ärger__Zürich.md' in names, str(names))
    rep.check('ZIP enthält die manifest.json', '2026-01-02/manifest.json' in names)


def parse_like_frontend(content: str) -> dict:
    """Nachbau von parseMarkdown aus frontend/src/components/ZipLoader.jsx."""
    lines = content.split('\n')
    out = {'title': '', 'date': '', 'category': 'allgemein', 'url': '', 'summary': ''}
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith('# ') and not out['title']:
            out['title'] = line[2:].strip()
        elif 'Datum:' in line:
            m = re.search(r'\*?\*?Datum:\*?\*?\s*(.+)', line)
            out['date'] = m.group(1).strip() if m else ''
        elif 'Kategorie:' in line:
            m = re.search(r'\*?\*?Kategorie:\*?\*?\s*(.+)', line)
            out['category'] = m.group(1).strip() if m else ''
        elif 'Zusammenfassung:' in line:
            m = re.search(r'\*?\*?Zusammenfassung:\*?\*?\s*(.+)', line)
            out['summary'] = m.group(1).strip() if m else ''
        elif 'Original auf NZZ.ch öffnen' in line or 'URL:' in line:
            m = re.search(r'\[.*?\]\((https?://[^)]+)\)', line)
            out['url'] = m.group(1).strip() if m else ''
        elif line.startswith('---'):
            body_start = i + 1
            break
    out['body'] = '\n'.join(lines[body_start:])
    return out


def check_browser(rep, cfg):
    section('Mobilgerät-Emulation')
    with BrowserSession(cfg) as s:
        page = s.new_page()
        page.set_content('<meta name="viewport" content="width=device-width,initial-scale=1">')
        ua = page.evaluate('navigator.userAgent')
        rep.check('User-Agent ist mobil', 'Mobile' in ua and 'Android' in ua, ua[:60])
        rep.equals('Layout-Breite 412px', page.evaluate('window.screen.width'), 412)
        rep.check('Touch verfügbar', page.evaluate('navigator.maxTouchPoints') > 0)
        rep.equals('Zeitzone Europe/Zurich',
                   page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone"),
                   'Europe/Zurich')
        rep.check('Sprache deutsch', page.evaluate('navigator.language').startswith('de'))
        rep.check('navigator.webdriver maskiert',
                  page.evaluate('navigator.webdriver') in (None, False))


def check_consent(rep, cfg, ctx):
    section('Cookie-Consent')
    with BrowserSession(cfg) as s:
        home = HomePage(s.new_page(), ctx)
        home.open().wait_until_ready()
        overlay = CookieConsentOverlay(home.page, ctx)
        # is_present() wartet auf das CMP-Skript; sense() schaut nur einmal hin.
        present = overlay.is_present()
        rep.check('Banner wird erkannt', present, overlay.sense().reason)
        if present:
            rep.check('accept() entfernt das Banner', overlay.accept())
            rep.check('Sensor meldet es danach als weg', not overlay.sense().verdict)


def check_pagetype(rep, cfg, ctx):
    section('Seitentyp-Erkennung')
    sensor = PageTypeSensor()
    with BrowserSession(cfg) as s:
        page = s.new_page()

        home = HomePage(page, ctx)
        home.open().wait_until_ready()
        home.dismiss_overlays()
        rep.equals('Startseite → HOME',
                   sensor.read(home, ctx).extra.get('page_type'), PageType.HOME)

        feed = LatestArticlesPage(page, ctx)
        feed.open(cfg.base_url).wait_until_ready()
        rep.equals('/neueste-artikel → FEED',
                   sensor.read(feed, ctx).extra.get('page_type'), PageType.FEED)

        links = feed.collect_links(max_links=5, max_rounds=1)
        if links:
            art = ArticlePage(page, ctx)
            art.open(links[0]).wait_until_ready()
            rep.equals('Artikel-URL → ARTICLE',
                       sensor.read(art, ctx).extra.get('page_type'), PageType.ARTICLE)

        bogus = ArticlePage(page, ctx)
        bogus.open('https://www.nzz.ch/gibt-es-nicht-ld.99999999')
        actual = sensor.read(bogus, ctx).extra.get('page_type')
        rep.check('Unbekannte URL ist NICHT ARTICLE', actual is not PageType.ARTICLE, str(actual))

        rep.check('BlockingSensor meldet keine Blockade',
                  not BlockingSensor().read(feed, ctx).verdict)


def check_login(rep, cfg, ctx, debug):
    section('Login von null')
    if cfg.session_file.exists():
        cfg.session_file.unlink()
    with BrowserSession(cfg) as s:
        auth = AuthManager(s, cfg, debug, ctx)
        state = auth.ensure_logged_in(s.new_page())
        rep.check('Login erfolgreich', state.logged_in, state.sensor.reason)
        rep.equals('Weg war der Piano-Flow', state.via, 'piano')
        rep.check('Konfidenz mindestens 0.6', state.sensor.confidence >= 0.6,
                  f'{state.sensor.confidence:.2f}')
        rep.check('Mindestens zwei unabhängige Signale',
                  len(state.sensor.positive()) >= 2,
                  ', '.join(sig.name for sig in state.sensor.positive()))
    rep.check('Session-Datei angelegt', cfg.session_file.exists())
    if cfg.session_file.exists():
        rep.equals('Session-Datei ist 0600',
                   oct(cfg.session_file.stat().st_mode)[-3:], '600')
        rep.check('Session-Datei enthält Cookies',
                  bool(json.loads(cfg.session_file.read_text()).get('cookies')))


def check_session(rep, cfg, ctx, debug):
    section('Login aus gespeicherter Session')
    if not cfg.session_file.exists():
        rep.skip('Wiederverwendung der Session', 'keine Session-Datei aus dem Login-Schritt')
        return
    started = time.monotonic()
    with BrowserSession(cfg) as s:
        auth = AuthManager(s, cfg, debug, ctx)
        state = auth.ensure_logged_in(s.new_page())
        elapsed = time.monotonic() - started
        rep.check('Eingeloggt ohne Piano-Formular', state.logged_in and state.via == 'storage_state',
                  state.via)
        rep.equals('Kein Re-Login nötig', auth.relogin_attempts, 0)
        rep.check('Schneller als 15s', elapsed < 15, f'{elapsed:.1f}s')


def check_relogin(rep, cfg, ctx, debug):
    section('Re-Login-Fallback')
    with BrowserSession(cfg) as s:
        auth = AuthManager(s, cfg, debug, ctx)
        page = s.new_page()
        auth.ensure_logged_in(page)
        s.context.clear_cookies()                       # Session künstlich entwerten
        after = auth.check(page)
        rep.check('Verlorene Session wird erkannt', not after.at_least(0.6), after.reason)
        state = auth.relogin(page)
        rep.check('Re-Login stellt die Session wieder her', state.logged_in,
                  state.sensor.reason)
        rep.equals('Genau ein Re-Login gezählt', auth.relogin_attempts, 1)


def check_feed(rep, cfg, ctx):
    section('Artikelliste')
    with BrowserSession(cfg) as s:
        feed = LatestArticlesPage(s.new_page(), ctx)
        feed.open(cfg.base_url).assert_ready()
        feed.dismiss_overlays()
        initial = len(feed._hrefs())
        links = feed.collect_links(max_links=25, max_rounds=6)
        rep.check('Mindestens 10 Artikel-Links', len(links) >= 10, str(len(links)))
        rep.check('Alle Links passen auf das Artikel-Muster',
                  all(ARTICLE_URL_RE.match(u) for u in links),
                  next((u for u in links if not ARTICLE_URL_RE.match(u)), ''))
        rep.equals('Keine Dubletten', len(set(links)), len(links))
        rep.check('Kein /information/-Fehltreffer',
                  not any('/information/' in u for u in links))
        rep.check('Scrollen hat nachgeladen', len(feed._hrefs()) > initial,
                  f'{initial} → {len(feed._hrefs())} <a>')
        return links


def check_article(rep, cfg, ctx, debug, links):
    section('Artikel end-to-end (eingeloggt)')
    if not links:
        rep.skip('Artikel-Extraktion', 'keine Links aus dem Feed')
        return
    with BrowserSession(cfg) as s:
        page = s.new_page()
        AuthManager(s, cfg, debug, ctx).ensure_logged_in(page)
        art = ArticlePage(page, ctx)
        art.open(links[0]).assert_ready()
        art.dismiss_overlays()
        raw = art.extract()
        markdown = html_fragment_to_markdown(raw.html)

        rep.check('Titel ist gesetzt', bool(raw.title.strip()), raw.title[:50])
        rep.check('Titel ist nicht der Seitentitel', raw.title.strip() != page.title().strip())
        rep.check('Datum ist ISO-parsebar', _parsable(raw.published_at), raw.published_at)
        rep.check('Mindestens 500 Zeichen Inhalt', len(markdown) >= 500, str(len(markdown)))
        rep.check('Kein Rückfall auf <article>', not raw.used_fallback, raw.matched_selector)
        rep.check('Piano hat entschieden', raw.settle.decision_seen)

        quality = ContentQualitySensor().read(raw, markdown, page_title=page.title())
        rep.check('Qualitätssensor grün', bool(quality), quality.reason)
        paywall = PaywallSensor().read(art, ctx, raw=raw, content_chars=len(markdown))
        rep.check('Keine Paywall (wir sind eingeloggt)', not paywall.verdict, paywall.reason)


def check_paywall(rep, cfg, ctx, links):
    section('Paywall-Erkennung (ohne Login)')
    if not links:
        rep.skip('Paywall-Erkennung', 'keine Links aus dem Feed')
        return
    from dataclasses import replace
    anon_cfg = replace(cfg, force_anonymous=True)
    anon_ctx, _ = make_ctx(anon_cfg)

    with BrowserSession(anon_cfg) as s:
        found = False
        for url in links[:10]:
            page = s.new_page()
            art = ArticlePage(page, anon_ctx)
            art.open(url).assert_ready()
            art.dismiss_overlays()
            raw = art.extract()
            markdown = html_fragment_to_markdown(raw.html)
            result = PaywallSensor().read(art, anon_ctx, raw=raw, content_chars=len(markdown))
            page.close()
            if result.verdict:
                found = True
                rep.check('Paywall-Artikel wird anonym erkannt', True,
                          f'{raw.settle.initial_size}→{raw.settle.final_size} Zeichen')
                break
        if not found:
            # Kein Fehler: es kann sein, dass gerade alle Artikel frei sind.
            rep.skip('Paywall-Erkennung',
                     'unter den ersten 10 Artikeln war keiner hinter der Paywall')


def check_run(rep, cfg):
    section('Vollständiger Lauf und Tracking')
    from dataclasses import replace
    # 200 Links einzusammeln dauert ~20 Scrollrunden; für den Test reicht die
    # erste Feed-Seite.
    cfg = replace(cfg, max_links=20)
    result = ScraperRun(cfg).execute(limit=2)
    rep.equals('Lauf endet mit Exit 0', result.exit_code, 0)
    rep.check('Mindestens ein Artikel gespeichert', result.saved >= 1, str(result.saved))

    tracking = json.loads(cfg.tracking_file.read_text())
    entries = tracking['articles']
    rep.check('Tracking-Einträge vorhanden', bool(entries))
    for entry in entries:
        rep.check(f'Pflichtfelder in {entry["title"][:28]}',
                  {'url', 'scraped_date', 'scraped_at', 'filename', 'title'} <= set(entry))
        rep.check(f'Datei auffindbar: {Path(entry["filename"]).name[:28]}',
                  (cfg.output_dir / entry['filename']).exists())

    second = ScraperRun(cfg).execute(limit=2)
    already = {e['url'] for e in entries}
    rep.check('Zweiter Lauf scrapt keine bekannten URLs erneut',
              all(u not in already for u in _urls(cfg)[len(entries):]) if second.saved else True)
    rep.equals('Zweiter Lauf endet mit Exit 0', second.exit_code, 0)


def _urls(cfg):
    return [e['url'] for e in json.loads(cfg.tracking_file.read_text())['articles']]


def check_debug(rep, cfg, ctx):
    section('Debug-Artefakte')
    before = len(list(cfg.debug_dir.glob('*'))) if cfg.debug_dir.exists() else 0
    with BrowserSession(cfg) as s:
        art = ArticlePage(s.new_page(), ctx)
        try:
            art.open('https://www.nzz.ch/gibt-es-nicht-ld.99999999').assert_ready()
        except Exception:
            pass
        art.capture_debug('smoke-test')
    dirs = sorted(d for d in cfg.debug_dir.iterdir() if d.is_dir())
    rep.check('Debug-Verzeichnis wurde angelegt', len(dirs) > before, str(len(dirs)))
    if dirs:
        latest = dirs[-1]
        rep.check('screenshot.png vorhanden', (latest / 'screenshot.png').exists())
        rep.check('page.html vorhanden', (latest / 'page.html').exists())
        meta = json.loads((latest / 'meta.json').read_text())
        rep.check('meta.json nennt die URL', 'url' in meta, meta.get('url', '')[:50])


def _parsable(value: str) -> bool:
    from dateutil import parser
    try:
        parser.parse(value)
        return True
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description='Live-Smoke-Test für den NZZ-Scraper')
    ap.add_argument('--headed', action='store_true')
    ap.add_argument('--keep-artifacts', action='store_true')
    ap.add_argument('--with-ai', action='store_true', help='OpenRouter mitlaufen lassen')
    ap.add_argument('--only', default='', help=f'Kommaliste aus: {", ".join(SECTIONS)}')
    ap.add_argument('--log-level', default='WARNING')
    args = ap.parse_args()

    wanted = set(args.only.split(',')) if args.only else set(SECTIONS)
    unknown = wanted - set(SECTIONS)
    if unknown:
        print(f'Unbekannte Abschnitte: {", ".join(sorted(unknown))}')
        return 2

    if not args.with_ai:
        # Kein Tokenverbrauch und keine 2s-Ratelimit-Pausen im Test.
        os.environ['OPENROUTER_API_KEY'] = ''

    rep = SkipAwareReport()
    tmp = Path(tempfile.mkdtemp(prefix='nzz-scraper-smoke-'))
    prod_articles = snapshot(BACKEND / 'articles')
    prod_state = snapshot(BACKEND / '.state')

    cfg = ScraperConfig.from_env(
        output_dir=tmp / 'articles', session_file=tmp / 'state.json',
        debug_dir=tmp / 'debug', log_file=tmp / 'scraper.log',
        headless=not args.headed, use_ai=args.with_ai)
    cfg.ensure_dirs()
    setup_logging(args.log_level, cfg.log_file)

    # Sicherheitsnetz gegen eine Config-Regression, bevor irgendetwas läuft.
    assert cfg.output_dir.is_relative_to(tmp), cfg.output_dir
    assert cfg.session_file.is_relative_to(tmp), cfg.session_file
    assert cfg.debug_dir.is_relative_to(tmp), cfg.debug_dir

    have_creds = bool(cfg.email and cfg.password)
    ctx, debug = make_ctx(cfg)
    links = []

    print(f'\033[1mNZZ-Scraper Smoke-Test\033[0m  (Arbeitsverzeichnis: {tmp})')
    try:
        if 'output' in wanted:
            check_output_compat(rep, cfg)
        if 'browser' in wanted:
            check_browser(rep, cfg)
        if 'consent' in wanted:
            check_consent(rep, cfg, ctx)
        if 'pagetype' in wanted:
            check_pagetype(rep, cfg, ctx)

        for name, fn in (('login', check_login), ('session', check_session),
                         ('relogin', check_relogin)):
            if name not in wanted:
                continue
            if not have_creds:
                rep.skip(f'Abschnitt {name}', 'NZZ_EMAIL/NZZ_PASSWORD nicht gesetzt')
                continue
            fn(rep, cfg, ctx, debug)

        if 'feed' in wanted:
            links = check_feed(rep, cfg, ctx)
        if 'article' in wanted:
            if have_creds:
                check_article(rep, cfg, ctx, debug, links)
            else:
                rep.skip('Abschnitt article', 'NZZ_EMAIL/NZZ_PASSWORD nicht gesetzt')
        if 'paywall' in wanted:
            check_paywall(rep, cfg, ctx, links)
        if 'tracking' in wanted:
            if have_creds:
                check_run(rep, cfg)
            else:
                rep.skip('Abschnitt tracking', 'NZZ_EMAIL/NZZ_PASSWORD nicht gesetzt')
        if 'debug' in wanted:
            check_debug(rep, cfg, ctx)

        if 'isolation' in wanted:
            section('Produktionsdaten unberührt')
            rep.equals('backend/articles/ unverändert', snapshot(BACKEND / 'articles'),
                       prod_articles)
            rep.equals('backend/.state/ unverändert', snapshot(BACKEND / '.state'),
                       prod_state)

    except Exception as e:
        import traceback
        print(f'\n\033[31mAbbruch:\033[0m {type(e).__name__}: {e}')
        traceback.print_exc()
        rep.failed.append(f'Ausführung abgebrochen: {e}')
    finally:
        if args.keep_artifacts:
            print(f'\nArtefakte: {tmp}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    return rep.summary()


if __name__ == '__main__':
    sys.exit(main())
