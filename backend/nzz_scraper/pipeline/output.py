"""Schreiben der Artefakte: Markdown, ZIP, Manifest.

ACHTUNG – Kompatibilitätsvertrag. Das Frontend (frontend/src/components/
ZipLoader.jsx, parseMarkdown) parst den Markdown-Kopf zeilenweise und bricht bei
der ersten Zeile ab, die mit '---' beginnt. flask_server.py leitet das Datum aus
dem ZIP-Dateinamen ab und liest manifest.json. Reihenfolge, Marker und
Dateinamens-Ableitung dürfen sich deshalb nicht ändern.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Sequence

from ..logging_setup import get_logger
from ..models import Article

log = get_logger(__name__)

_UNSAFE_TITLE = re.compile(r'[^\w\s-]')


def sanitize_summary(summary: str) -> str:
    """Erzwingt eine einzige Zeile.

    ZipLoader.jsx liest die Zusammenfassung mit einer zeilenweisen else-if-Kette;
    ein Zeilenumbruch darin würde den Rest des Kopfes verschieben.
    """
    return ' '.join(summary.split()) if summary else ''


def filename_for(title: str) -> str:
    """Dateiname aus dem Titel – wörtlich wie im alten Scraper."""
    safe_title = _UNSAFE_TITLE.sub('', title)[:50].strip()
    return f"{safe_title.replace(' ', '_')}.md"


def render_markdown(article: Article) -> str:
    """Erzeugt den Dateiinhalt. Kopfzeilen exakt wie bisher."""
    parts = [
        f"# {article.title}\n\n",
        f"**[→ Original auf NZZ.ch öffnen]({article.url})**\n\n",
        f"**Datum:** {article.date}\n\n",
        f"**Kategorie:** {article.category}\n\n",
    ]
    summary = sanitize_summary(article.summary)
    if summary:
        parts.append(f"**Zusammenfassung:** {summary}\n\n")
    parts.append("---\n\n")
    parts.append(article.content)
    return ''.join(parts)


class ArticleWriter:
    """Schreibt Artikel nach <output_dir>/<datum>/<kategorie>/<Titel>.md."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def write(self, article: Article, date_folder: Path) -> Path:
        cat_folder = date_folder / article.category
        cat_folder.mkdir(parents=True, exist_ok=True)

        filename = filename_for(article.title)
        article.filename = filename                 # für das Tracking
        filepath = cat_folder / filename
        filepath.write_text(render_markdown(article), encoding='utf-8')
        return filepath

    def write_all(self, articles: Sequence[Article], date_folder: Path) -> int:
        saved = 0
        for article in articles:
            if article is None:
                continue
            self.write(article, date_folder)
            saved += 1
        return saved


def create_zip(date_folder: Path) -> Path:
    """Erstellt/überschreibt das Tages-ZIP neben dem Tagesordner."""
    zip_path = date_folder.with_suffix('.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(date_folder.rglob('*')):
            if file_path.is_file():
                arcname = file_path.relative_to(date_folder.parent)
                zf.write(file_path, arcname)

    log.info('ZIP erstellt: %s', zip_path, extra={'icon': '✓'})
    return zip_path


def update_manifest(date_folder: Path) -> Path:
    """Zählt ALLE .md im Tagesordner – nicht nur die neu gescrapten."""
    categories: dict[str, int] = {}
    total = 0

    for cat_folder in sorted(date_folder.iterdir()):
        if cat_folder.is_dir():
            article_count = len(list(cat_folder.glob('*.md')))
            if article_count > 0:
                categories[cat_folder.name] = article_count
                total += article_count

    manifest = {
        'date': date_folder.name,
        'total_articles': total,
        'categories': categories,
    }

    manifest_path = date_folder / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    log.info('Manifest aktualisiert: %s (%d Artikel)', manifest_path, total,
             extra={'icon': '✓'})
    return manifest_path
