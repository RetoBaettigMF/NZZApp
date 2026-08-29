"""Cookie-Consent-Overlay.

Wird ohne force=True geklickt und danach verifiziert. Der alte Scraper klickte
den Anmelden-Button mit force=True durch das Overlay hindurch – der Klick landete
nirgends und der Fehler zeigte sich erst Sekunden später am Piano-iframe.
"""
from __future__ import annotations

from ..logging_setup import get_logger
from ..models import PageType
from ..sensors.consent import ConsentSensor
from . import locators as L
from .base import BasePage

log = get_logger(__name__)


class CookieConsentOverlay(BasePage):
    page_type = PageType.CONSENT_OVERLAY
    ready_selectors = L.CONSENT_BOX

    _sensor = ConsentSensor()

    def sense(self):
        return self._sensor.read(self, self.ctx)

    def is_present(self, *, wait_ms: int = 4000) -> bool:
        """Prüft auf ein Banner und wartet kurz darauf.

        Das CMP-Skript hängt sich asynchron ein – es ist regelmässig noch nicht
        da, wenn der Seitenkopf schon steht. Ein einmaliger Blick meldet dann
        fälschlich "kein Banner", und der nächste Klick landet im Overlay.
        """
        if self.sense().verdict:
            return True
        try:
            self.page.locator(L.CONSENT_BOX[0]).first.wait_for(
                state='visible', timeout=wait_ms)
        except Exception:
            return False
        return bool(self.sense())

    def accept(self, *, verify: bool = True) -> bool:
        """Klickt Zustimmen und prüft, dass das Banner wirklich weg ist."""
        try:
            button = self.first_visible('consent.accept', L.CONSENT_ACCEPT,
                                        timeout_ms=self.cfg.selector_timeout_ms)
        except Exception as e:
            log.warning('Kein Consent-Button gefunden: %s', e)
            return False

        button.click()
        try:
            self.page.wait_for_load_state('networkidle', timeout=8000)
        except Exception:
            pass

        if not verify:
            return True

        after = self.sense()
        if after.verdict:
            log.warning('Consent-Banner nach dem Klick weiterhin präsent: %s', after.describe())
            self.capture_debug('consent-persists', sensors=[after])
            return False

        log.info('Cookie-Consent akzeptiert', extra={'icon': '✓'})
        return True
