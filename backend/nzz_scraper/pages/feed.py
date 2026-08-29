"""Artikelliste /neueste-artikel – Infinite Scroll."""
from __future__ import annotations

import time
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..errors import TransientScrapeError
from ..logging_setup import get_logger
from ..models import FeedEntry, PageType
from . import locators as L
from .base import BasePage

log = get_logger(__name__)


class LatestArticlesPage(BasePage):
    page_type = PageType.FEED
    url_pattern = L.FEED_PATH
    # 'a[href]' taugt nicht: die ersten Treffer sind Sprungmarken (href="#").
    # Bereit ist der Feed, wenn mindestens ein Artikel-Link im DOM steht.
    ready_selectors = ()

    def wait_until_ready(self, timeout_ms: int | None = None):
        timeout_ms = timeout_ms or self.cfg.default_timeout_ms
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if any(self.is_article_href(h) for h in self._hrefs()):
                return self
            self.page.wait_for_timeout(300)
        self.capture_debug('feed-no-links')
        raise TransientScrapeError(
            f'Kein einziger Artikel-Link auf {self.page.url} innert {timeout_ms}ms')

    @staticmethod
    def is_article_href(href: str | None) -> bool:
        if not href or not L.ARTICLE_HREF.match(href):
            return False
        # /information/impressum-ld.148422 passt auf die Regex, ist kein Artikel.
        return not href.startswith(L.NON_ARTICLE_PREFIXES)

    def _entries(self) -> list[dict]:
        """href plus Pro-Markierung aus dem zugehörigen Teaser-Kasten.

        Die Prüfung ist bewusst auf den Teaser begrenzt: im ganzen Seitentext zu
        suchen liefert Fehltreffer, weil auch Standard-Artikel Pro-Beiträge als
        Empfehlung einblenden.
        """
        try:
            return self.page.evaluate("""(label) => {
                const out = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (!href) return;
                    const box = a.closest('article') || a.parentElement;
                    const text = (box && box.innerText) || '';
                    out.push({href, pro: text.includes(label)});
                });
                return out;
            }""", L.FEED_PRO_LABEL) or []
        except PlaywrightError:
            return []

    def _hrefs(self) -> list[str]:
        return [e['href'] for e in self._entries()]

    def _collect(self, into: dict) -> int:
        before = len(into)
        for entry in self._entries():
            href = entry['href']
            if self.is_article_href(href):
                url = urljoin(L.SITE_ROOT, href)
                # Einmal als Pro erkannt bleibt Pro: derselbe Artikel kann in
                # mehreren Kästen auftauchen, nicht alle tragen das Label.
                into[url] = into.get(url, False) or bool(entry['pro'])
        return len(into) - before

    def _load_more(self) -> bool:
        """Scrollt ans Ende und wartet darauf, dass die Seite wächst."""
        height = self.page.evaluate('document.body.scrollHeight')
        self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        try:
            self.page.wait_for_function(
                'h => document.body.scrollHeight > h', arg=height, timeout=6000)
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            return False

    def collect_links(self, **kwargs) -> list[str]:
        """Nur die URLs – für Aufrufer, die die Abo-Stufe nicht brauchen."""
        return [e.url for e in self.collect_entries(**kwargs)]

    def collect_entries(self, *, max_links: int = 200, max_rounds: int = 20,
                        stall_rounds: int = 3) -> list[FeedEntry]:
        """Sammelt Artikel-URLs über Infinite Scroll.

        Der Feed wächst nicht monoton – einzelne Runden liefern nichts, die
        nächste wieder ein Dutzend. stall_rounds ist deshalb > 2.
        """
        links: dict[str, bool] = {}
        self._collect(links)
        stalled = 0

        for round_no in range(1, max_rounds + 1):
            if len(links) >= max_links:
                break
            grew = self._load_more()
            new = self._collect(links)
            log.debug('Scroll-Runde %d: +%d Links (total %d, Höhe wuchs=%s)',
                      round_no, new, len(links), grew)
            stalled = stalled + 1 if new == 0 else 0
            if stalled >= stall_rounds:
                log.debug('%d Runden ohne neue Links – Ende', stalled)
                break

        entries = [FeedEntry(url, is_pro) for url, is_pro in links.items()][:max_links]
        pro_count = sum(1 for e in entries if e.is_pro)
        log.info('%d Artikel-Links gefunden (%d davon NZZ Pro)', len(entries), pro_count,
                 extra={'icon': '✓'})
        return entries
