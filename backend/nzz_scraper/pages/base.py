"""BasePage – gemeinsamer Vertrag aller Page-Models.

Zwei Prinzipien:

* Es wird auf *Zustände* gewartet (expect/wait_for), nie auf Uhrzeiten.
  wait_for_timeout ist im ganzen Paket verboten.
* Klicks laufen ohne force=True. Braucht ein Klick force, liegt ein Overlay
  darüber – das ist ein Bug, kein Workaround.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar, Sequence

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..config import ScraperConfig
from ..debug import DebugArtifacts
from ..errors import LocatorChainExhausted, TransientScrapeError, UnexpectedPageError
from ..logging_setup import get_logger
from ..models import PageType

log = get_logger(__name__)


@dataclass
class PageContext:
    """Alles, was ein Page-Model ausser der Playwright-Page braucht."""

    cfg: ScraperConfig
    debug: DebugArtifacts
    page_type_sensor: object | None = None      # wird von sensors.page_type gesetzt
    notes: list[str] = field(default_factory=list)


class BasePage:
    """Basisklasse aller Seiten."""

    page_type: ClassVar[PageType] = PageType.UNKNOWN
    url_pattern: ClassVar[re.Pattern | None] = None
    ready_selectors: ClassVar[tuple[str, ...]] = ()
    default_url: ClassVar[str | None] = None

    def __init__(self, page: Page, ctx: PageContext):
        self.page = page
        self.ctx = ctx
        self.cfg = ctx.cfg
        self._response: Response | None = None

    # ---------------------------------------------------------------- Navigation

    def open(self, url: str | None = None, *, wait_until: str = 'domcontentloaded'):
        target = url or self.default_url or self.cfg.site_root
        log.debug('goto %s', target)
        try:
            # Die Response wird aufgehoben: ohne sie kann der BlockingSensor
            # HTTP 403/429 gar nicht sehen.
            self._response = self.page.goto(target, wait_until=wait_until)
        except PlaywrightTimeoutError as e:
            raise TransientScrapeError(f'Timeout beim Laden von {target}: {e}') from e
        except PlaywrightError as e:
            # ERR_ABORTED heisst meist: die Seite hat selbst weiternavigiert
            # (Piano tut das direkt nach dem Login). Kein Fehler, solange wir
            # auf der erwarteten Origin gelandet sind.
            if 'ERR_ABORTED' in str(e) and self.page.url.startswith(self.cfg.site_root):
                log.debug('goto abgebrochen, Seite navigierte selbst nach %s', self.page.url)
                self._response = None
            else:
                raise TransientScrapeError(
                    f'Navigation nach {target} fehlgeschlagen: {e}') from e
        return self

    @property
    def last_response(self) -> Response | None:
        return self._response

    @property
    def status(self) -> int | None:
        try:
            return self._response.status if self._response else None
        except PlaywrightError:
            return None

    @property
    def url(self) -> str:
        return self.page.url

    # ---------------------------------------------------------------- Zustand

    def is_current(self) -> bool:
        """Billige Prüfung: URL-Muster plus ein sichtbarer Marker. Wartet nicht."""
        if self.url_pattern and not self.url_pattern.search(self.page.url):
            return False
        if not self.ready_selectors:
            return True
        return self.any_present(self.ready_selectors) is not None

    def wait_until_ready(self, timeout_ms: int | None = None):
        """Wartet, bis einer der ready_selectors sichtbar ist."""
        if not self.ready_selectors:
            return self
        self.first_visible(
            f'{type(self).__name__}.ready', self.ready_selectors,
            timeout_ms=timeout_ms or self.cfg.selector_timeout_ms)
        return self

    def assert_ready(self, timeout_ms: int | None = None):
        """wait_until_ready plus Gegenprobe durch den PageTypeSensor.

        Verhindert, dass eine 404- oder Consent-Seite durch die Selektorkaskade
        rutscht und als Artikel gespeichert wird.
        """
        self.wait_until_ready(timeout_ms)
        sensor = self.ctx.page_type_sensor
        if sensor is not None and self.page_type is not PageType.UNKNOWN:
            result = sensor.read(self, self.ctx)
            actual = result.extra.get('page_type')
            if actual is not None and actual != self.page_type:
                self.capture_debug(f'unexpected-{actual}', sensors=[result])
                raise UnexpectedPageError(self.page_type, actual, self.page.url, result.reason)
        return self

    # ---------------------------------------------------------------- Locators

    def first_visible(self, name: str, selectors: Sequence[str], *,
                      timeout_ms: int | None = None,
                      scope: Locator | None = None) -> Locator:
        """Erster sichtbarer Treffer der dokumentierten Kette.

        Loggt auf DEBUG, welcher Kandidat gegriffen hat – damit nach einem
        NZZ-Redesign in einer Logzeile steht, welche Kette gebrochen ist.
        """
        timeout_ms = timeout_ms or self.cfg.selector_timeout_ms
        root = scope if scope is not None else self.page
        for selector in selectors:
            try:
                loc = root.locator(selector).first
                loc.wait_for(state='visible', timeout=timeout_ms)
                log.debug('%s ← %r', name, selector)
                return loc
            except (PlaywrightTimeoutError, PlaywrightError):
                continue
        self.capture_debug(f'locator-{name}')
        raise LocatorChainExhausted(name, selectors, self.page.url)

    def any_present(self, selectors: Sequence[str], *,
                    scope: Locator | None = None) -> str | None:
        """Gibt den ersten Selektor zurück, der ein sichtbares Element trifft."""
        root = scope if scope is not None else self.page
        for selector in selectors:
            try:
                if root.locator(selector).first.is_visible(timeout=250):
                    return selector
            except (PlaywrightTimeoutError, PlaywrightError):
                continue
        return None

    def count(self, selector: str) -> int:
        try:
            return self.page.locator(selector).count()
        except PlaywrightError:
            return 0

    def safe_eval(self, expression: str, arg=None, default=None):
        """page.evaluate, das bei Fehlern `default` liefert statt zu werfen."""
        try:
            return self.page.evaluate(expression, arg)
        except PlaywrightError as e:
            log.debug('evaluate fehlgeschlagen (%s): %s', expression[:60], e)
            return default

    def settle(self, timeout_ms: int = 12_000) -> None:
        """Wartet auf Netzwerkruhe. Ein Timeout ist kein Fehler."""
        try:
            self.page.wait_for_load_state('networkidle', timeout=timeout_ms)
        except (PlaywrightTimeoutError, PlaywrightError):
            log.debug('networkidle nicht erreicht innert %dms', timeout_ms)

    # ---------------------------------------------------------------- Overlays

    def dismiss_overlays(self) -> bool:
        """Schliesst das Cookie-Banner, falls eines da ist. True = etwas getan."""
        from .consent import CookieConsentOverlay

        overlay = CookieConsentOverlay(self.page, self.ctx)
        if overlay.is_present():
            return overlay.accept()
        return False

    # ---------------------------------------------------------------- Inhalt

    def html(self) -> str:
        return self.page.content()

    def soup(self, scope: Locator | None = None) -> BeautifulSoup:
        """BeautifulSoup über den *Container*, nicht über die ganze Seite.

        Playwright findet den Container, BeautifulSoup konvertiert ihn – so wird
        nicht bei jedem Aufruf das komplette Seiten-HTML neu geparst.
        """
        markup = scope.inner_html() if scope is not None else self.page.content()
        return BeautifulSoup(markup, 'html.parser')

    def text(self, scope: Locator | None = None) -> str:
        try:
            if scope is not None:
                return scope.inner_text()
            return self.page.locator('body').inner_text()
        except PlaywrightError:
            return ''

    # ---------------------------------------------------------------- Debug

    def capture_debug(self, label: str, *, error: BaseException | None = None,
                      sensors: Sequence = ()):
        return self.ctx.debug.capture(self.page, label, error=error, sensors=sensors,
                                      extra={'page': type(self).__name__,
                                             'status': self.status})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.capture_debug(f'{type(self).__name__.lower()}-error', error=exc)
        return False
