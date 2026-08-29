"""Retry mit exponentiellem Backoff und Jitter."""
from __future__ import annotations

import random
import time
from typing import Callable, Sequence, TypeVar

from .errors import TransientScrapeError
from .logging_setup import get_logger

T = TypeVar('T')
log = get_logger(__name__)

DEFAULT_RETRY_ON: tuple[type[BaseException], ...] = (TransientScrapeError,)


def with_retry(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 2.0,
               factor: float = 2.0, jitter: float = 0.3,
               retry_on: Sequence[type[BaseException]] = DEFAULT_RETRY_ON,
               deadline: float | None = None,
               on_retry: Callable[[int, BaseException], None] | None = None) -> T:
    """Ruft `fn` bis zu `attempts` mal auf.

    Args:
        deadline: `time.monotonic()`-Zeitpunkt, ab dem nicht mehr wiederholt wird.
        retry_on: Exception-Typen, die einen Retry auslösen. Alles andere fliegt sofort.
    """
    retry_on = tuple(retry_on)
    last: BaseException | None = None

    for attempt in range(1, attempts + 1):
        if deadline is not None and time.monotonic() >= deadline:
            log.warning('Zeitbudget erschöpft vor Versuch %d/%d', attempt, attempts)
            break
        try:
            return fn()
        except retry_on as exc:
            last = exc
            if attempt >= attempts:
                break
            delay = base_delay * (factor ** (attempt - 1))
            delay *= 1 + random.uniform(-jitter, jitter)
            if deadline is not None and time.monotonic() + delay >= deadline:
                log.warning('Zeitbudget reicht nicht für Backoff von %.1fs – Abbruch', delay)
                break
            if on_retry:
                on_retry(attempt, exc)
            else:
                log.warning('Versuch %d/%d fehlgeschlagen (%s) – warte %.1fs',
                            attempt, attempts, exc, delay)
            time.sleep(delay)

    assert last is not None
    raise last
