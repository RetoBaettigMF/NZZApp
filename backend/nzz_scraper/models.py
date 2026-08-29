"""Datentypen des Scrapers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PageType(StrEnum):
    """Seitentypen, die der PageTypeSensor unterscheidet."""

    HOME = 'home'
    FEED = 'feed'
    ARTICLE = 'article'
    PIANO_LOGIN = 'piano_login'
    CONSENT_OVERLAY = 'consent_overlay'
    PAYWALL = 'paywall'
    NOT_FOUND = 'not_found'
    BLOCKED = 'blocked'
    UNKNOWN = 'unknown'


@dataclass
class ContentSettle:
    """Grössenverlauf des Artikel-Containers rund um den Piano-Zugriffsentscheid."""

    initial_size: int          # grösster gesehener Stand (serverseitig gerendert)
    final_size: int            # Stand nach dem Entscheid
    decision_seen: bool        # hat Piano überhaupt geurteilt?

    SHRINK_THRESHOLD = 0.6     # final < 60% des Maximums = gekürzt

    @property
    def shrink_ratio(self) -> float:
        if self.initial_size <= 0:
            return 1.0
        return self.final_size / self.initial_size

    @property
    def shrank(self) -> bool:
        return self.initial_size > 0 and self.shrink_ratio < self.SHRINK_THRESHOLD


@dataclass
class RawArticle:
    """Rohextraktion einer Artikelseite, vor Markdown-Konvertierung und AI."""

    url: str
    title: str
    published_at: str          # ISO-8601
    html: str                  # inner_html des Artikel-Containers
    matched_selector: str = ''
    used_fallback: bool = False
    settle: ContentSettle | None = None


@dataclass
class Article:
    """Fertiger Artikel, wie er geschrieben und getrackt wird."""

    title: str
    url: str
    date: str                  # ISO-8601
    category: str
    content: str
    summary: str = ''
    filename: str | None = None
    ai_cleaned: bool = False
    content_chars: int = 0
    matched_selector: str = ''

    def __post_init__(self):
        if not self.content_chars:
            self.content_chars = len(self.content)

    def to_legacy_dict(self) -> dict:
        """Exakt die sechs Keys des alten Scrapers – Kompatibilitätsanker."""
        return {
            'title': self.title,
            'url': self.url,
            'date': self.date,
            'category': self.category,
            'content': self.content,
            'summary': self.summary,
        }


@dataclass
class RunResult:
    """Bilanz eines Laufs."""

    links_found: int = 0
    new_links: int = 0
    scraped: int = 0
    saved: int = 0
    skipped_paywalled: int = 0
    skipped_quality: int = 0
    failed: int = 0
    relogins: int = 0
    duration_s: float = 0.0
    exit_code: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def summary_line(self) -> str:
        return (
            f"{self.saved} gespeichert · {self.skipped_paywalled} Paywall · "
            f"{self.skipped_quality} Qualität · {self.failed} Fehler · "
            f"{self.relogins} Re-Logins · {self.duration_s:.0f}s"
        )
