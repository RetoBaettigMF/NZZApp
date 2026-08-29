"""PageTypeSensor – auf welcher Seite stehen wir?

Wird nach jedem goto() in BasePage.assert_ready() konsultiert. Ohne ihn rutscht
eine 404- oder Consent-Seite durch die Selektorkaskade und wird als Artikel
gespeichert.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..models import PageType
from ..pages import locators as L
from .types import Signal, SensorResult, combine


class PageTypeSensor:
    name = 'page_type'

    def read(self, page, ctx) -> SensorResult:
        url = page.url
        path = urlparse(url).path
        status = page.status
        meta = page.safe_eval(L.JS_META, default={}) or {}
        signals: list[Signal] = []

        def sig(name: str, fired: bool, weight: float, detail: str = ''):
            signals.append(Signal(name, fired, weight, detail))

        # --- harte Signale zuerst: HTTP-Status
        if status is not None:
            if status in (403, 429, 503):
                sig('http_blocked', True, 1.0, str(status))
                return self._verdict(PageType.BLOCKED, signals, f'HTTP {status}')
            if status == 404:
                sig('http_404', True, 1.0, str(status))
                return self._verdict(PageType.NOT_FOUND, signals, 'HTTP 404')

        title = meta.get('title') or ''
        if any(t.lower() in title.lower() for t in L.BLOCKED_TEXTS):
            sig('blocked_title', True, 1.0, title[:60])
            return self._verdict(PageType.BLOCKED, signals, f'Titel: {title[:60]}')

        # --- Piano-Login
        if L.PIANO_URL.search(url) or page.any_present(L.PIANO_IFRAME):
            sig('piano', True, 1.0, 'iframe/url')
            return self._verdict(PageType.PIANO_LOGIN, signals, 'Piano-Login sichtbar')

        # --- Artikel: drei unabhängige Indizien
        og_type = (meta.get('og_type') or '').lower()
        ld_types = (meta.get('ld_types') or '')
        url_is_article = bool(L.ARTICLE_HREF.match(path)) and not any(
            path.startswith(p) for p in L.NON_ARTICLE_PREFIXES)

        sig('url_pattern', url_is_article, 0.30, path[:50])
        sig('og_article', og_type == 'article', 0.30, og_type)
        sig('ld_newsarticle', 'NewsArticle' in ld_types, 0.25, ld_types[:40])
        sig('h1_and_time', bool(meta.get('h1')) and bool(meta.get('has_time')), 0.15,
            (meta.get('h1') or '')[:40])

        article = combine('page_type.article', signals, threshold=0.5)
        if article.verdict:
            return self._verdict(PageType.ARTICLE, signals, article.reason,
                                 confidence=article.confidence)

        # --- Feed / Home
        if L.FEED_PATH.search(path):
            signals.append(Signal('feed_path', True, 1.0, path))
            return self._verdict(PageType.FEED, signals, 'Pfad /neueste-artikel')
        if path in ('', '/'):
            signals.append(Signal('root_path', True, 1.0, path))
            return self._verdict(PageType.HOME, signals, 'Wurzelpfad')

        if not meta:
            return SensorResult(self.name, None, 0.0, tuple(signals),
                                'Seite nicht auswertbar', {'page_type': None})

        return self._verdict(PageType.UNKNOWN, signals, article.reason,
                             confidence=article.confidence)

    @staticmethod
    def _verdict(page_type: PageType, signals, reason: str,
                 confidence: float = 1.0) -> SensorResult:
        return SensorResult(
            sensor='page_type',
            verdict=page_type is not PageType.UNKNOWN,
            confidence=confidence,
            signals=tuple(signals),
            reason=f'{page_type}: {reason}',
            extra={'page_type': page_type},
        )
