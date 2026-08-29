"""ConsentSensor – liegt ein Cookie-Banner über der Seite?"""
from __future__ import annotations

from ..pages import locators as L
from .types import Signal, SensorResult, combine


class ConsentSensor:
    name = 'consent'

    def read(self, page, ctx) -> SensorResult:
        box = page.any_present(L.CONSENT_BOX)
        accept = page.any_present(L.CONSENT_ACCEPT)
        scroll_locked = bool(page.safe_eval(L.JS_BODY_SCROLL_LOCKED, default=False))

        signals = [
            Signal('consent_box', box is not None, 0.45, box or ''),
            Signal('accept_button', accept is not None, 0.40, accept or ''),
            Signal('scroll_locked', scroll_locked, 0.15),
        ]
        return combine(self.name, signals, threshold=0.4)
