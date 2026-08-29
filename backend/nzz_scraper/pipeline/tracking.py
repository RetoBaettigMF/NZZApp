"""Persistentes Tracking bereits gescrapter Artikel.

Format von articles/scraped_articles.json bleibt unverändert – migrate_tracking.py
und delete_recent_articles hängen daran. Felder hinzufügen ist sicher,
entfernen/umbenennen nicht.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..logging_setup import get_logger
from ..models import Article

log = get_logger(__name__)


class TrackingStore:
    """Hält die Tracking-Liste und einen URL-Index.

    Der alte Scraper baute in is_article_scraped() bei *jedem* Link ein neues Set
    über alle Artikel. Hier wird der Index einmal beim Laden gefüllt.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {'articles': [], 'last_updated': None}
        self._urls: set[str] = set()

    def load(self) -> "TrackingStore":
        if not self.path.exists():
            self.data = {'articles': [], 'last_updated': None}
        else:
            try:
                self.data = json.loads(self.path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                log.warning('Tracking-Datei beschädigt, erstelle neue: %s', self.path)
                self.data = {'articles': [], 'last_updated': None}
        self.data.setdefault('articles', [])
        self._urls = {a['url'] for a in self.data['articles'] if 'url' in a}
        log.info('%d Artikel bereits gescrapt', len(self._urls))
        return self

    def save(self) -> None:
        self.data['last_updated'] = datetime.now().isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding='utf-8')
        log.info('Tracking aktualisiert: %d Artikel total', len(self.data['articles']),
                 extra={'icon': '✓'})

    def is_scraped(self, url: str) -> bool:
        return url in self._urls

    def add(self, article: Article, date_str: str) -> None:
        """Fügt einen Eintrag hinzu. Die fünf Pflichtfelder bleiben unverändert."""
        self.data['articles'].append({
            'url': article.url,
            'scraped_date': date_str,
            'scraped_at': datetime.now().isoformat(),
            'filename': f"{date_str}/{article.category}/{article.filename or 'unknown.md'}",
            'title': article.title,
            # Zusätzliche Felder sind rückwärtskompatibel:
            'content_chars': article.content_chars,
            'ai_cleaned': article.ai_cleaned,
        })
        self._urls.add(article.url)

    def delete_recent(self, hours: int, output_dir: Path) -> tuple[int, set[str]]:
        """Löscht Artikel der letzten N Stunden und deren Dateien.

        Returns:
            (Anzahl entfernter Einträge, betroffene Datumsordner-Namen)
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        urls_to_remove: set[str] = set()
        affected_dates: set[str] = set()

        for article in self.data['articles']:
            remove = False
            scraped_at = article.get('scraped_at')
            if scraped_at:
                try:
                    remove = datetime.fromisoformat(scraped_at) >= cutoff
                except ValueError:
                    pass

            filepath = output_dir / article.get('filename', '')
            if not remove and filepath.exists():
                # Fallback für Alt-Einträge ohne scraped_at
                remove = datetime.fromtimestamp(filepath.stat().st_mtime) >= cutoff

            if remove:
                urls_to_remove.add(article['url'])
                affected_dates.add(article.get('scraped_date', ''))
                if filepath.exists():
                    filepath.unlink()
                    log.debug('Gelöscht: %s', filepath.name)

        before = len(self.data['articles'])
        self.data['articles'] = [
            a for a in self.data['articles'] if a['url'] not in urls_to_remove]
        self._urls -= urls_to_remove
        removed = before - len(self.data['articles'])
        affected_dates.discard('')
        return removed, affected_dates

    @property
    def count(self) -> int:
        return len(self.data['articles'])
