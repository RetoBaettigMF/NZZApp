"""Artikelseite.

Zwei Eigenheiten von NZZ mobil (siehe MOBILE_SELECTORS.md):

* `article` (das HTML-Tag) umfasst nur einen ~320-Zeichen-Teaser. Der Fliesstext
  steht in `section.container--article`. Die Selektorkette ist entsprechend
  sortiert; `article` steht ganz hinten.
* Die Paywall greift clientseitig rund zwei Sekunden nach dem Laden: erst liefert
  der Server den Volltext, dann ersetzt Piano ihn durch den Anriss. Es wird
  deshalb auf DOM-Stabilität gewartet, bevor extrahiert wird.
"""
from __future__ import annotations

import time
from datetime import datetime

from dateutil import parser as date_parser
from playwright.sync_api import Error as PlaywrightError

from ..errors import TransientScrapeError
from ..logging_setup import get_logger
from ..models import ContentSettle, PageType, RawArticle
from . import locators as L
from .base import BasePage

log = get_logger(__name__)


class ArticlePage(BasePage):
    page_type = PageType.ARTICLE
    url_pattern = L.ARTICLE_URL
    ready_selectors = L.ARTICLE_TITLE

    # ---------------------------------------------------------------- Warten

    _SIZE_JS = """(sels) => {
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el) return el.innerHTML.length;
        }
        return -1;
    }"""

    # Piano liefert erst nach einigen hundert ms ein Urteil. Solange
    # isUserValid() nicht definiert ist, ist der Zugriffsentscheid offen.
    _DECISION_JS = """() => {
        try {
            if (typeof window.tp === 'undefined') return null;
            const u = window.tp.user;
            if (u && typeof u.isUserValid === 'function') return !!u.isUserValid();
            return null;
        } catch (e) { return null; }
    }"""

    def wait_for_stable_content(self, *, timeout_s: float = 20.0,
                                quiet_ms: int = 1800, interval_ms: int = 350) -> ContentSettle:
        """Wartet den Zugriffsentscheid ab und danach die DOM-Ruhe.

        Die NZZ-Seite wird serverseitig mit dem Volltext ausgeliefert; Piano
        entscheidet clientseitig über den Zugriff und ersetzt den Container
        gegebenenfalls durch den Anriss. Gemessen (anonym, Pro-Artikel):

            0.65s  48273 Zeichen HTML   tp noch nicht da
            2.84s  48783 Zeichen HTML   tp = false   (networkidle!)
            3.84s  16151 Zeichen HTML   Anriss

        Wer bei "zweimal gleiche Grösse" oder bei networkidle aufhört, greift
        den Text *vor* dem Zugriffsentscheid ab. Deshalb wird zuerst auf den
        Entscheid gewartet und erst danach auf eine Ruhephase.

        Der Grössenverlauf ist zugleich das Paywall-Signal: schrumpft der
        Container nach dem Entscheid deutlich, wurde die Paywall angewandt.
        """
        selectors = list(L.ARTICLE_BODY)
        deadline = time.monotonic() + timeout_s

        initial = self._read_size(selectors)
        peak = max(initial, 0)
        decided = False
        last_size = initial
        last_change = time.monotonic()

        while time.monotonic() < deadline:
            self.page.wait_for_timeout(interval_ms)

            if not decided:
                decided = self.safe_eval(self._DECISION_JS, default=None) is not None

            size = self._read_size(selectors)
            peak = max(peak, size)
            if size != last_size:
                last_size, last_change = size, time.monotonic()
                continue

            quiet_for = (time.monotonic() - last_change) * 1000
            if decided and quiet_for >= quiet_ms:
                break
        else:
            log.debug('Inhalt nicht stabil innert %.0fs (zuletzt %d)', timeout_s, last_size)

        settle = ContentSettle(initial_size=peak, final_size=last_size,
                               decision_seen=decided)
        if settle.shrank:
            log.debug('Container schrumpfte %d -> %d (%.0f%%) – Paywall angewandt',
                      peak, last_size, 100 * settle.shrink_ratio)
        return settle

    def _read_size(self, selectors) -> int:
        return self.safe_eval(self._SIZE_JS, selectors, default=-1) or -1

    # ---------------------------------------------------------------- Felder

    def body(self):
        return self.first_visible('article.body', L.ARTICLE_BODY,
                                  timeout_ms=self.cfg.selector_timeout_ms)

    def title(self) -> str:
        try:
            return self.first_visible('article.title', L.ARTICLE_TITLE,
                                      timeout_ms=2000).inner_text().strip()
        except Exception:
            return (self.page.title() or 'Unbekannter Titel').strip()

    def published_at(self) -> datetime:
        try:
            value = self.page.locator(L.ARTICLE_TIME[0]).first.get_attribute(
                'datetime', timeout=2000)
            if value:
                return date_parser.parse(value)
        except (PlaywrightError, ValueError, TypeError):
            pass
        return datetime.now()

    # ---------------------------------------------------------------- Extraktion

    def extract(self) -> RawArticle:
        """Liest den Artikel aus. Meldet mit, welcher Selektor gegriffen hat."""
        settle = self.wait_for_stable_content()

        matched, container = '', None
        for selector in L.ARTICLE_BODY:
            try:
                loc = self.page.locator(selector).first
                if loc.count() and loc.is_visible(timeout=500):
                    matched, container = selector, loc
                    break
            except PlaywrightError:
                continue

        if container is None:
            self.capture_debug('article-no-body')
            raise TransientScrapeError(f'Kein Artikel-Container auf {self.page.url}')

        # `article` ist der Notnagel und ein starkes Negativsignal für die Qualität.
        used_fallback = matched in ('article', 'main article')

        try:
            html = container.inner_html()
        except PlaywrightError as e:
            raise TransientScrapeError(f'Container nicht lesbar: {e}') from e

        log.debug('Artikel-Container ← %r (%d Zeichen HTML)', matched, len(html))

        return RawArticle(
            url=self.page.url,
            title=self.title(),
            published_at=self.published_at().isoformat(),
            html=html,
            matched_selector=matched,
            used_fallback=used_fallback,
            settle=settle,
        )
