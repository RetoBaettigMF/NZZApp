"""ContentQualitySensor – ist das ein vollständiger Artikel?"""
from __future__ import annotations

from ..extraction.markdown import link_text_ratio, paragraph_count
from .types import Signal, combine

MIN_CHARS = 500          # Schwelle des alten Scrapers, bewusst übernommen
MIN_PARAGRAPHS = 3
MAX_LINK_RATIO = 0.30


class ContentQualitySensor:
    name = 'content_quality'

    def read(self, raw, markdown: str, *, page_title: str = ''):
        chars = len(markdown)
        paragraphs = paragraph_count(markdown)
        ratio = link_text_ratio(raw.html)

        title_ok = bool(raw.title) and raw.title.strip() != page_title.strip()

        signals = [
            Signal('length', chars >= MIN_CHARS, 0.25, f'{chars} Zeichen'),
            Signal('paragraphs', paragraphs >= MIN_PARAGRAPHS, 0.20, str(paragraphs)),
            Signal('title', title_ok, 0.15, raw.title[:40]),
            Signal('has_date', bool(raw.published_at), 0.10, raw.published_at[:19]),
            # Hoher Linkanteil entlarvt Übersichts- statt Artikelseiten.
            Signal('link_ratio', ratio < MAX_LINK_RATIO, 0.15, f'{ratio:.0%}'),
            # Rückfall auf `article`/`main` heisst: der echte Container fehlte.
            Signal('no_fallback', not raw.used_fallback, 0.15, raw.matched_selector),
        ]
        return combine(self.name, signals, threshold=0.6)
