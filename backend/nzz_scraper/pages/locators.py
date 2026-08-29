"""Selektorketten für www.nzz.ch im Mobilprofil.

Ermittelt am 2026-08-29 mit `python -m nzz_scraper.tools.explore` gegen
www.nzz.ch, Profil 'Pixel 7'. Vollständiges Protokoll: MOBILE_SELECTORS.md.

Reihenfolge = Priorität. Prioritätsregeln:
  1. ARIA / Accessible Name   – NZZ ist gut ausgezeichnet
  2. semantische Marker-Klassen (container--article) – kein Tailwind
  3. Struktur (h1, time[datetime])
  4. Text zuletzt – bricht bei A/B-Tests und Sprachvarianten

NZZ nutzt Tailwind-Utilities und hat KEIN data-testid. Exakte Klassennamen sind
darum tabu; nur die zwei semantischen Marker oben sind stabil.
"""
from __future__ import annotations

import re
from typing import Final

# ------------------------------------------------------------------ URLs

SITE_ROOT: Final = 'https://www.nzz.ch'

# Artikel-URLs: /<ressort>/<slug>-ld.<id>
ARTICLE_HREF: Final = re.compile(r'^/[\w-]+/[\w-]+\.\d+$')
ARTICLE_URL: Final = re.compile(r'^https://www\.nzz\.ch/[\w-]+/[\w-]+\.\d+$')
FEED_PATH: Final = re.compile(r'/neueste-artikel')
PIANO_URL: Final = re.compile(r'id-eu\.piano\.io')

# /information/impressum-ld.148422 passt auf die Artikel-Regex, ist aber keiner.
NON_ARTICLE_PREFIXES: Final = ('/information/', '/impressum', '/agb', '/datenschutz')

# ------------------------------------------------------------------ Consent

CONSENT_BOX: Final = (
    '#cmpbox[role="dialog"]',
    '#cmpbox',
    '[id*="cmp"][role="dialog"]',
    '[class*="consent"][role="dialog"]',
)

CONSENT_ACCEPT: Final = (
    '#cmpwelcomebtnyes',
    '#cmpbox a#cmpwelcomebtnyes',
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Akzeptieren")',
    'button:has-text("Einverstanden")',
)

# ------------------------------------------------------------------ Kopfzeile

HEADER: Final = ('header#header', 'header')

# Mobil direkt sichtbar, NICHT hinter dem Hamburger.
LOGIN_BUTTON: Final = (
    'button[aria-label="Anmelden"]',
    '[aria-label="Anmelden"]',
    'header button:has-text("Anmelden")',
)

BURGER_BUTTON: Final = (
    'button[aria-label="Menü öffnen"]',
    'button[aria-label*="Menü"]',
    'header button[aria-expanded]',
)

# Nach dem Login ersetzt NZZ den Anmelden-Button durch einen Konto-Einstieg.
# ACHTUNG: 'a[href*="konto"]' war hier und feuerte auch im anonymen Zustand
# (Footer-Link "Abonnemente"). Nur Elemente, die es ohne Login nicht gibt.
ACCOUNT_INDICATORS: Final = (
    'button[aria-label="User menu"]',        # ersetzt eingeloggt den Anmelden-Button
    'header button[aria-label*="User"]',
    'button[aria-label="Mein Konto"]',
    'button[aria-label*="Mein Konto"]',
    'button[aria-label*="Profil"]',
    'a[href*="/mein-konto"]',
    '[aria-label*="Abmelden"]',
)

SECTION_NAV: Final = ('nav[aria-label="Rubriken"]', 'nav')

# ------------------------------------------------------------------ Piano-Login

PIANO_IFRAME: Final = (
    'iframe[src*="id-eu.piano.io"]',
    'iframe[name^="piano-id"]',
    'iframe[src*="piano.io"]',
)

PIANO_EMAIL: Final = (
    'input[name="email"]',
    'input[type="email"]',
    'input[autocomplete="username"]',
)

PIANO_PASSWORD: Final = (
    'input[type="password"]',
    'input[name="password"]',
)

PIANO_SUBMIT: Final = (
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Anmelden")',
)

PIANO_ERROR: Final = (
    '[class*="error"]',
    '[role="alert"]',
    '[class*="Error"]',
)

# reCAPTCHA läuft im Piano-Frame mit – Treffer heisst: manuell eingreifen.
CAPTCHA: Final = (
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    'iframe[src*="turnstile"]',
    '[class*="captcha"]',
)

# ------------------------------------------------------------------ Artikel

# Reihenfolge ist entscheidend: `article` steht bewusst HINTEN.
# section.container--article = 6589 Zeichen, article = 320 Zeichen (Teaser).
ARTICLE_BODY: Final = (
    'section.container--article',
    '[class*="container--article"]',
    'div.article section',
    'div.article',
    '[class*="articleContent"]',
    'main article',
    'article',
)

ARTICLE_TITLE: Final = ('h1',)

ARTICLE_TIME: Final = ('time[datetime]', 'time')

# Empfehlungsblöcke und Randspalten, die nicht in den Fliesstext gehören.
ARTICLE_NOISE: Final = (
    '[class*="recommended-for-you"]',
    '[class*="webview-bta"]',
    '[class*="newsletter"]',
    '[class*="teaser-list"]',
    'aside',
    'figure',
)

# ------------------------------------------------------------------ Paywall

# NICHT als Paywall-Signal verwenden: "NZZ abonnieren" ist ein globaler CTA und
# steht auch auf frei lesbaren Artikeln (gemessen: cta_count=1 auf beiden, und
# nie innerhalb des Artikel-Containers). Nur noch informativ.
PAYWALL_CTA: Final = (
    'button:has-text("NZZ abonnieren")',
    'a:has-text("NZZ abonnieren")',
    'button:has-text("Jetzt abonnieren")',
    'a:has-text("Angebot")',
)

PAYWALL_CONTAINER: Final = (
    '[class*="paywall"]',
    '[class*="regwall"]',
    '[id*="paywall"]',
    '[class*="barrier"]',
)

# ------------------------------------------------------------------ Blockade

BLOCKED_TEXTS: Final = (
    'Just a moment',
    'Access Denied',
    'Zugriff verweigert',
    'Bitte bestätigen Sie',
    'unusual traffic',
)

# ------------------------------------------------------------------ JS-Sonden

# Piano legt window.tp an; isUserValid() ist das belastbarste Login-Signal.
JS_TP_USER_VALID: Final = """
() => {
  try {
    if (typeof window.tp === 'undefined') return null;
    if (window.tp.user && typeof window.tp.user.isUserValid === 'function')
      return !!window.tp.user.isUserValid();
    if (window.tp.pianoId && typeof window.tp.pianoId.isUserValid === 'function')
      return !!window.tp.pianoId.isUserValid();
    return null;
  } catch (e) { return null; }
}
"""

JS_LOCAL_STORAGE_KEYS: Final = """
() => { try { return Object.keys(localStorage); } catch (e) { return []; } }
"""

JS_BODY_SCROLL_LOCKED: Final = """
() => {
  try {
    const s = getComputedStyle(document.body);
    return s.overflow === 'hidden' || s.position === 'fixed';
  } catch (e) { return false; }
}
"""

JS_META: Final = """
() => ({
  og_type: document.querySelector('meta[property="og:type"]')?.content || null,
  ld_types: [...document.querySelectorAll('script[type="application/ld+json"]')]
    .map(s => { try { const j = JSON.parse(s.textContent);
                      return Array.isArray(j) ? j.map(x => x['@type']).join(',')
                                              : String(j['@type'] || ''); }
                catch (e) { return ''; } }).join(','),
  h1: document.querySelector('h1')?.innerText?.trim() || '',
  has_time: !!document.querySelector('time[datetime]'),
  title: document.title || '',
})
"""

# Cookie-Namen, die eine Piano-/NZZ-Sitzung belegen (Präfix-Vergleich).
SESSION_COOKIE_HINTS: Final = ('__utp', '__tbc', 'xbc', '_pc_', 'pnespsdk',
                               'nzz_session', 'PIANO', 'piano')
