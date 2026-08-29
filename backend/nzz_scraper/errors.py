"""Fehlertaxonomie des Scrapers.

Die Klassenhierarchie steuert die Retry-Politik: alles unter
:class:`TransientScrapeError` wird wiederholt, der Rest nicht.
"""
from __future__ import annotations

from typing import Sequence


class ScraperError(Exception):
    """Basisklasse aller Scraper-Fehler."""


class ConfigError(ScraperError):
    """Konfiguration unvollständig oder widersprüchlich."""


class TransientScrapeError(ScraperError):
    """Vorübergehender Fehler – ein Retry ist sinnvoll."""


class LocatorChainExhausted(TransientScrapeError):
    """Keiner der dokumentierten Selektoren hat gegriffen.

    Trägt die vollständige Kette mit, damit nach einem NZZ-Redesign in einer
    einzigen Logzeile steht, welche Kette gebrochen ist.
    """

    def __init__(self, name: str, selectors: Sequence[str], url: str):
        self.name = name
        self.selectors = tuple(selectors)
        self.url = url
        super().__init__(
            f"Selektorkette '{name}' erschöpft auf {url} "
            f"({len(self.selectors)} Kandidaten: {', '.join(self.selectors)})"
        )


class UnexpectedPageError(ScraperError):
    """Der PageTypeSensor meldet einen anderen Seitentyp als erwartet.

    Kein Retry: die Seite ist, was sie ist.
    """

    def __init__(self, expected, actual, url: str, reason: str = ''):
        self.expected = expected
        self.actual = actual
        self.url = url
        super().__init__(
            f"Erwartet {expected}, erhalten {actual} auf {url}"
            + (f" – {reason}" if reason else '')
        )


class PaywallError(ScraperError):
    """Artikel steckt hinter der Paywall – Re-Login prüfen, dann überspringen."""

    def __init__(self, url: str, confidence: float = 0.0):
        self.url = url
        self.confidence = confidence
        super().__init__(f"Paywall erkannt auf {url} (Konfidenz {confidence:.2f})")


class LoginFailedError(ScraperError):
    """Login endgültig gescheitert – Lauf abbrechen (Exit 2)."""


class BlockedError(ScraperError):
    """Von NZZ blockiert oder rate-limitiert – Lauf abbrechen (Exit 3)."""


# Exit-Codes des CLI
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_LOGIN = 2
EXIT_BLOCKED = 3
