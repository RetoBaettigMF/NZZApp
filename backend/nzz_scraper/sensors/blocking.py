"""BlockingSensor – blockiert oder rate-limitiert uns NZZ?

Der alte Scraper warf das Response-Objekt von page.goto() weg und konnte 403/429
darum gar nicht sehen.
"""
from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError

from ..pages import locators as L
from .types import Signal, combine

BLOCKING_STATUS = (403, 429, 503)


class BlockingSensor:
    name = 'blocked'

    def read(self, page, ctx):
        status = page.status
        response = page.last_response

        retry_after = None
        if response is not None:
            try:
                retry_after = response.headers.get('retry-after')
            except PlaywrightError:
                pass

        try:
            title = page.page.title()
        except PlaywrightError:
            title = ''
        text_hit = next((t for t in L.BLOCKED_TEXTS if t.lower() in title.lower()), None)

        captcha = page.any_present(L.CAPTCHA)

        body_len = page.safe_eval('() => document.body.innerText.length', default=None)
        thin = bool(status == 200 and body_len is not None and body_len < 2000)

        signals = [
            Signal('http_status', status in BLOCKING_STATUS, 0.40, str(status)),
            Signal('retry_after', retry_after is not None, 0.15, retry_after or ''),
            Signal('blocked_text', text_hit is not None, 0.20, text_hit or ''),
            Signal('captcha', captcha is not None, 0.15, captcha or ''),
            Signal('thin_body', thin, 0.10, str(body_len)),
        ]
        return combine(self.name, signals, threshold=0.35)
