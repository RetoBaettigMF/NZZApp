#!/usr/bin/env python3
"""Explorationshelfer: dumpt eine NZZ-Seite im Mobilgerät-Profil.

Die mobilen Selektoren lassen sich nicht raten – dieses Werkzeug sammelt die
Rohdaten, aus denen pages/locators.py gefüllt wird.

    backend/venv/bin/python -m nzz_scraper.tools.explore --url https://www.nzz.ch
    backend/venv/bin/python -m nzz_scraper.tools.explore --url ... --headed --pause

Schreibt nach <debug_dir>/explore/<ts>-<slug>/:
    page.html · screenshot.png · cookies.json · storage.json
    tp_state.json · candidates.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nzz_scraper.browser import BrowserSession                       # noqa: E402
from nzz_scraper.config import ScraperConfig                         # noqa: E402
from nzz_scraper.logging_setup import get_logger, setup_logging      # noqa: E402

log = get_logger(__name__)

# Sammelt Elemente, die für Artikel, Paywall, Consent und Navigation relevant sind.
CANDIDATE_JS = r"""
() => {
  const vis = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const desc = el => ({
    tag: el.tagName.toLowerCase(),
    id: el.id || undefined,
    cls: (typeof el.className === 'string' ? el.className : '').slice(0, 160) || undefined,
    testid: el.getAttribute('data-testid') || undefined,
    role: el.getAttribute('role') || undefined,
    aria: el.getAttribute('aria-label') || undefined,
    visible: vis(el),
    chars: (el.innerText || '').trim().length,
    text: (el.innerText || '').trim().slice(0, 100) || undefined,
  });

  const out = {};

  out.testids = [...new Set([...document.querySelectorAll('[data-testid]')]
    .map(e => e.getAttribute('data-testid')))].slice(0, 200);

  out.data_attrs = [...new Set([].concat(...[...document.querySelectorAll('*')].map(e =>
    [...e.attributes].map(a => a.name).filter(n => n.startsWith('data-') &&
      !['data-testid'].includes(n)))))].slice(0, 120);

  out.buttons = [...document.querySelectorAll('button,[role="button"],a[href]')]
    .filter(vis)
    .map(e => ({...desc(e), href: e.getAttribute('href') || undefined}))
    .filter(e => (e.text && e.text.length < 60) || e.aria)
    .slice(0, 120);

  const byPattern = (pat) => [...document.querySelectorAll('*')]
    .filter(e => {
      const c = typeof e.className === 'string' ? e.className : '';
      return pat.test(c) || pat.test(e.id || '') || pat.test(e.getAttribute('data-testid') || '');
    }).map(desc).slice(0, 60);

  out.article_like = byPattern(/article|content|body|text|story/i);
  out.paywall_like = byPattern(/paywall|piano|subscri|abo|regwall|premium/i);
  out.consent_like = byPattern(/consent|cookie|cmp|gdpr|sourcepoint/i);
  out.nav_like     = byPattern(/burger|hamburger|menu|nav|account|login|profil|anmeld/i);

  out.iframes = [...document.querySelectorAll('iframe')].map(e => ({
    src: (e.getAttribute('src') || '').slice(0, 200),
    id: e.id || undefined, cls: (e.className || '').slice(0, 80) || undefined,
    visible: vis(e),
  }));

  out.landmarks = [...document.querySelectorAll('main,article,header,nav,footer,[role]')]
    .map(desc).slice(0, 60);

  out.meta = {
    title: document.title,
    og_type: document.querySelector('meta[property="og:type"]')?.content,
    og_url: document.querySelector('meta[property="og:url"]')?.content,
    viewport: document.querySelector('meta[name="viewport"]')?.content,
    ldjson_types: [...document.querySelectorAll('script[type="application/ld+json"]')]
      .map(s => { try { const j = JSON.parse(s.textContent);
                        return Array.isArray(j) ? j.map(x => x['@type']).join(',') : j['@type']; }
                  catch(e) { return 'unparsable'; } }),
    body_overflow: getComputedStyle(document.body).overflow,
    body_chars: (document.body.innerText || '').length,
    h1: [...document.querySelectorAll('h1')].map(e => e.innerText.trim().slice(0,120)),
    time_tags: [...document.querySelectorAll('time')].map(e => e.getAttribute('datetime')).slice(0,10),
  };

  return out;
}
"""

TP_STATE_JS = r"""
() => {
  const out = {has_tp: typeof window.tp !== 'undefined'};
  if (!out.has_tp) return out;
  try {
    out.tp_keys = Object.keys(window.tp).slice(0, 80);
    if (window.tp.user) {
      out.user_keys = Object.keys(window.tp.user).slice(0, 60);
      for (const fn of ['isUserValid', 'getUser', 'isLoggedIn']) {
        if (typeof window.tp.user[fn] === 'function') {
          try { out['user.' + fn] = JSON.parse(JSON.stringify(window.tp.user[fn]())); }
          catch (e) { out['user.' + fn] = 'error: ' + e.message; }
        }
      }
    }
    if (window.tp.pianoId) {
      out.pianoId_keys = Object.keys(window.tp.pianoId).slice(0, 60);
      for (const fn of ['isUserValid', 'getUser']) {
        if (typeof window.tp.pianoId[fn] === 'function') {
          try { out['pianoId.' + fn] = JSON.parse(JSON.stringify(window.tp.pianoId[fn]())); }
          catch (e) { out['pianoId.' + fn] = 'error: ' + e.message; }
        }
      }
    }
  } catch (e) { out.error = e.message; }
  return out;
}
"""

STORAGE_JS = r"""
() => {
  const grab = s => { const o = {}; try {
    for (let i = 0; i < s.length; i++) { const k = s.key(i);
      o[k] = (s.getItem(k) || '').slice(0, 300); } } catch(e) { o.__error = e.message; } return o; };
  return {localStorage: grab(localStorage), sessionStorage: grab(sessionStorage)};
}
"""


def slugify(url: str) -> str:
    p = urlparse(url)
    raw = (p.path or 'root').strip('/') or 'root'
    return re.sub(r'[^\w.-]+', '-', raw)[:40]


def explore(cfg: ScraperConfig, url: str, *, pause: bool, accept_consent: bool,
            scroll: bool) -> Path:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    target = cfg.debug_dir / 'explore' / f'{stamp}-{slugify(url)}'
    target.mkdir(parents=True, exist_ok=True)

    def dump(name: str, obj) -> None:
        (target / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False),
                                   encoding='utf-8')

    with BrowserSession(cfg) as session:
        page = session.new_page()
        log.info('Öffne %s', url)
        resp = page.goto(url, wait_until='domcontentloaded')
        dump('response.json', {'status': resp.status if resp else None,
                               'url': page.url,
                               'headers': dict(resp.headers) if resp else {}})
        page.wait_for_load_state('networkidle', timeout=15000)

        if accept_consent:
            for sel in ('#cmpwelcomebtnyes', 'button:has-text("Akzeptieren")',
                        'button:has-text("Alle akzeptieren")', 'button:has-text("Einverstanden")'):
                try:
                    page.locator(sel).first.click(timeout=2500)
                    log.info('Consent akzeptiert via %r', sel)
                    page.wait_for_load_state('networkidle', timeout=10000)
                    break
                except Exception:
                    continue

        if scroll:
            for _ in range(3):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                try:
                    page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    pass

        (target / 'page.html').write_text(page.content(), encoding='utf-8')
        try:
            page.screenshot(path=str(target / 'screenshot.png'), full_page=True)
        except Exception as e:
            log.warning('Screenshot fehlgeschlagen: %s', e)

        dump('cookies.json', session.cookies())
        dump('storage.json', page.evaluate(STORAGE_JS))
        dump('tp_state.json', page.evaluate(TP_STATE_JS))
        dump('candidates.json', page.evaluate(CANDIDATE_JS))

        if pause:
            log.info('page.pause() – Inspector offen, zum Fortfahren dort "Resume" klicken')
            page.pause()

    log.info('Exploration abgelegt in %s', target, extra={'icon': '✓'})
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='NZZ-Seite im Mobilprofil dumpen')
    ap.add_argument('--url', default='https://www.nzz.ch')
    ap.add_argument('--headed', action='store_true', help='sichtbarer Browser')
    ap.add_argument('--pause', action='store_true', help='Playwright-Inspector öffnen')
    ap.add_argument('--no-consent', action='store_true', help='Cookie-Banner stehen lassen')
    ap.add_argument('--scroll', action='store_true', help='dreimal ans Seitenende scrollen')
    ap.add_argument('--fresh', action='store_true', help='ohne gespeicherte Session')
    ap.add_argument('--device', default=None)
    ap.add_argument('--log-level', default='INFO')
    args = ap.parse_args(argv)

    setup_logging(args.log_level, log_file=None)
    overrides = {'headless': not args.headed, 'allow_anonymous': True}
    if args.device:
        overrides['device'] = args.device
    cfg = ScraperConfig.from_env(**overrides)
    cfg.ensure_dirs()
    if args.fresh and cfg.session_file.exists():
        cfg.session_file.unlink()

    explore(cfg, args.url, pause=args.pause,
            accept_consent=not args.no_consent, scroll=args.scroll)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
