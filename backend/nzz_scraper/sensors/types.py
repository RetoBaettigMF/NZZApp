"""Sensor-Protokoll und Ergebnistyp.

Ein Sensor liefert nie ein nacktes bool, sondern ein SensorResult mit den
einzelnen Signalen, einer Konfidenz und einer Begründung. Damit ist die
Behauptung falsifizierbar (der alte Scraper behauptete "eingeloggt", ohne es
belegen zu können) und `None` lässt sich von `False` unterscheiden:
"definitiv ausgeloggt" verlangt Re-Login, "konnte nicht feststellen" einen Retry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

DEFAULT_THRESHOLD = 0.5
CONFIDENT_THRESHOLD = 0.6


@dataclass(frozen=True)
class Signal:
    """Ein einzelnes Indiz."""

    name: str
    fired: bool
    weight: float
    detail: str = ''

    def __str__(self) -> str:
        mark = '+' if self.fired else '-'
        return f'{mark}{self.name}({self.weight:g})' + (f'[{self.detail}]' if self.detail else '')


@dataclass(frozen=True)
class SensorResult:
    """Verdikt eines Sensors samt Beweislage."""

    sensor: str
    verdict: bool | None                     # None = unbestimmt
    confidence: float
    signals: tuple[Signal, ...] = ()
    reason: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.verdict is True and self.confidence >= CONFIDENT_THRESHOLD

    def at_least(self, c: float) -> bool:
        """True, wenn positiv UND mindestens die geforderte Konfidenz erreicht."""
        return self.verdict is True and self.confidence >= c

    def positive(self) -> tuple[Signal, ...]:
        return tuple(s for s in self.signals if s.fired)

    def describe(self) -> str:
        return (f'{self.sensor}={self.verdict} ({self.confidence:.2f}) '
                f'[{" ".join(str(s) for s in self.signals)}]'
                + (f' – {self.reason}' if self.reason else ''))


def combine(sensor: str, signals: Sequence[Signal], *,
            threshold: float = DEFAULT_THRESHOLD, reason: str = '',
            extra: dict | None = None) -> SensorResult:
    """Gewichtete Summe der gefeuerten Signale / Summe aller Gewichte.

    Konnte kein einziges Signal ausgewertet werden (leere Liste), ist das
    Verdikt `None` – unbestimmt, nicht negativ.
    """
    signals = tuple(signals)
    if not signals:
        return SensorResult(sensor, None, 0.0, (), reason or 'kein Signal auswertbar',
                            extra or {})

    total = sum(s.weight for s in signals)
    if total <= 0:
        return SensorResult(sensor, None, 0.0, signals, 'Gewichtssumme 0', extra or {})

    confidence = sum(s.weight for s in signals if s.fired) / total
    verdict = confidence >= threshold
    if not reason:
        fired = [s.name for s in signals if s.fired]
        reason = ('Signale: ' + ', '.join(fired)) if fired else 'kein Signal gefeuert'
    return SensorResult(sensor, verdict, round(confidence, 4), signals, reason, extra or {})


def unknown(sensor: str, reason: str) -> SensorResult:
    """Sensor konnte nicht messen (Seite nicht geladen, Evaluate-Fehler …)."""
    return SensorResult(sensor, None, 0.0, (), reason)


class Sensor(Protocol):
    name: str

    def read(self, page, ctx) -> SensorResult: ...
