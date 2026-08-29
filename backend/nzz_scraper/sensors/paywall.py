"""PaywallSensor.

Behebt zwei Defekte des alten is_paywalled():
  * 'Abonnieren Sie' in soup.get_text() durchsuchte die ganze Seite und traf
    jeden Footer-Teaser.
  * Das Ergebnis wurde nur geprintet – der Anriss wurde trotzdem gespeichert
    UND getrackt, also nie wieder versucht.

Alle DOM-Signale sind auf den Artikel-Container gescoped.
"""
from __future__ import annotations

import statistics

from ..pages import locators as L
from .types import Signal, SensorResult, combine


class PaywallSensor:
    name = 'paywall'

    def __init__(self):
        self._lengths: list[int] = []

    def note_length(self, chars: int) -> None:
        """Meldet die Länge eines erfolgreich geholten Artikels (Laufmedian)."""
        if chars > 0:
            self._lengths.append(chars)

    @property
    def median(self) -> float | None:
        return statistics.median(self._lengths) if len(self._lengths) >= 3 else None

    def read(self, page, ctx, *, raw=None, content_chars: int | None = None) -> SensorResult:
        settle = getattr(raw, 'settle', None)

        container = page.any_present(L.PAYWALL_CONTAINER)
        tp_valid = page.safe_eval(L.JS_TP_USER_VALID, default=None)

        signals = [
            # Das kausale Signal: Piano hat den Container nach seinem
            # Zugriffsentscheid durch den Anriss ersetzt.
            Signal('content_shrank', bool(settle and settle.shrank), 0.50,
                   f'{settle.initial_size}->{settle.final_size}' if settle else 'nicht gemessen'),
            Signal('paywall_container', container is not None, 0.20, container or ''),
            Signal('not_entitled', tp_valid is False, 0.20,
                   f'tp.isUserValid()={tp_valid}'),
        ]

        median = self.median
        if median and content_chars is not None:
            short = content_chars < 0.4 * median
            signals.append(Signal('short_vs_median', short, 0.10,
                                  f'{content_chars} vs Median {median:.0f}'))

        return combine(self.name, signals, threshold=0.45)
