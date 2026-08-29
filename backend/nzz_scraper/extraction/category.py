"""Kategorie-Zuordnung – wörtlich aus scraper.py übernommen."""
from __future__ import annotations

CATEGORIES: dict[str, list[str]] = {
    'sport': ['sport', 'fussball', 'tennis', 'ski', 'formel 1'],
    'wirtschaft': ['wirtschaft', 'finanzen', 'börse', 'unternehmen', 'geld'],
    'wissenschaft': ['wissenschaft', 'forschung', 'technologie', 'medizin', 'gesundheit'],
    'lokal': ['zürich', 'schweiz', 'zuerich', 'bern', 'basel', 'genf'],
    'welt': ['international', 'ausland', 'europa', 'usa', 'asien'],
}

DEFAULT_CATEGORY = 'allgemein'


def extract_category(url: str, text: str = '') -> str:
    """Bestimmt die Kategorie aus URL, sonst aus den ersten 500 Textzeichen."""
    url_parts = url.replace('https://www.nzz.ch/', '').split('/')
    if url_parts:
        url_cat = url_parts[0].lower()
        for cat_name, keywords in CATEGORIES.items():
            if any(kw in url_cat or kw in url.lower() for kw in keywords):
                return cat_name

    lowered = text.lower()
    for cat_name, keywords in CATEGORIES.items():
        if any(kw in lowered[:500] for kw in keywords):
            return cat_name

    return DEFAULT_CATEGORY
