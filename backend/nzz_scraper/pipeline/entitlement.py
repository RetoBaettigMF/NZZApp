"""Abo-Stufe: Hat dieses Konto Zugriff auf NZZ-Pro-Artikel?

Piano verrät die Stufe nicht (window.tp.user.getUser() liefert null), also wird
sie empirisch ermittelt: ein Pro-Artikel wird geholt, und wenn Piano den Inhalt
kürzt, fehlt das Pro-Abo. Das Ergebnis wird zwischengespeichert und nach
`recheck_days` erneut geprüft – sonst würde ein späteres Upgrade nie auffallen.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger(__name__)


@dataclass
class Entitlement:
    has_pro: bool | None = None          # None = noch nicht ermittelt
    checked_at: str | None = None
    source: str = 'unbekannt'            # 'probe' | 'config'

    def is_fresh(self, recheck_days: int) -> bool:
        if self.has_pro is None or not self.checked_at:
            return False
        try:
            age = datetime.now() - datetime.fromisoformat(self.checked_at)
        except ValueError:
            return False
        return age < timedelta(days=recheck_days)

    def describe(self) -> str:
        if self.has_pro is None:
            return 'Pro-Zugriff unbekannt'
        state = 'vorhanden' if self.has_pro else 'nicht vorhanden'
        when = (self.checked_at or '')[:16].replace('T', ' ')
        return f'Pro-Abo {state} (ermittelt {when}, {self.source})'


class EntitlementStore:
    """Persistiert die erkannte Abo-Stufe neben der Login-Session."""

    def __init__(self, path: Path, recheck_days: int = 7):
        self.path = Path(path)
        self.recheck_days = recheck_days
        self.state = Entitlement()

    def load(self) -> Entitlement:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                self.state = Entitlement(
                    has_pro=raw.get('has_pro'),
                    checked_at=raw.get('checked_at'),
                    source=raw.get('source', 'unbekannt'))
            except (json.JSONDecodeError, TypeError):
                log.warning('Abo-Datei beschädigt, wird neu ermittelt: %s', self.path)
                self.state = Entitlement()
        return self.state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            'has_pro': self.state.has_pro,
            'checked_at': self.state.checked_at,
            'source': self.state.source,
        }, indent=2), encoding='utf-8')

    def set(self, has_pro: bool, source: str = 'probe') -> Entitlement:
        self.state = Entitlement(has_pro=has_pro,
                                 checked_at=datetime.now().isoformat(),
                                 source=source)
        self.save()
        log.info('%s', self.state.describe(), extra={'icon': '✓'})
        return self.state

    @property
    def needs_probe(self) -> bool:
        return not self.state.is_fresh(self.recheck_days)
