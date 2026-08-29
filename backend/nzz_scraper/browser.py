"""Browser-Session mit Mobilgerät-Emulation und Session-Persistenz.

Mobil, weil die NZZ-Seiten dort deutlich einfacher strukturiert sind.
Profil 'Pixel 7': Chromium-basiert (default_browser_type == 'chromium'), im
Gegensatz zu den iPhone-Profilen, die WebKit voraussetzen – ein WebKit-UA auf
einer Chromium-Engine ist eine erkennbare Inkonsistenz.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .config import ScraperConfig
from .logging_setup import get_logger

log = get_logger(__name__)

# Nur diese Keys aus dem Device-Descriptor gehören in new_context().
_CONTEXT_KEYS = ('user_agent', 'viewport', 'device_scale_factor', 'is_mobile', 'has_touch')


class BrowserSession:
    """Kapselt Playwright, Browser und den (mobilen) Kontext."""

    def __init__(self, cfg: ScraperConfig):
        self.cfg = cfg
        self._pw = None
        self._browser = None
        self._context = None
        self._tracing = False

    # ---------------------------------------------------------------- Lifecycle

    def start(self) -> "BrowserSession":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        launch_kwargs = {
            'headless': self.cfg.headless,
            'args': ['--disable-blink-features=AutomationControlled'],
        }
        if self.cfg.chromium_channel:
            launch_kwargs['channel'] = self.cfg.chromium_channel
        self._browser = self._pw.chromium.launch(**launch_kwargs)

        self._build_context(with_state=True)
        log.info('Browser gestartet: %s, headless=%s', self.cfg.device, self.cfg.headless,
                 extra={'icon': '✓'})
        return self

    def _device_args(self) -> dict:
        device = self._pw.devices.get(self.cfg.device)
        if device is None:
            raise ValueError(f"Unbekanntes Geräteprofil: {self.cfg.device!r}")
        if device.get('default_browser_type') not in (None, 'chromium'):
            log.warning("Geräteprofil %r ist für %s gedacht, wir fahren Chromium – "
                        "UA/Engine-Inkonsistenz möglich",
                        self.cfg.device, device['default_browser_type'])
        return {k: device[k] for k in _CONTEXT_KEYS if k in device}

    def _build_context(self, *, with_state: bool) -> None:
        state = self.cfg.session_file
        # force_anonymous heisst: auch keine gespeicherte Sitzung laden, sonst
        # startet der "anonyme" Lauf mit den Cookies des letzten Logins.
        use_state = (with_state and not self.cfg.force_anonymous
                     and state.exists() and state.stat().st_size > 0)

        self._context = self._browser.new_context(
            **self._device_args(),
            locale='de-CH',
            timezone_id='Europe/Zurich',
            color_scheme='light',
            reduced_motion='reduce',
            storage_state=str(state) if use_state else None,
        )
        self._context.set_default_timeout(self.cfg.default_timeout_ms)
        self._context.set_default_navigation_timeout(self.cfg.nav_timeout_ms)
        # Playwright setzt navigator.webdriver = true; das ist ein billiges Bot-Signal.
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        if use_state:
            log.info('Session aus %s geladen', state)
        if self.cfg.trace:
            self._context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self._tracing = True

    def reload_context(self, *, with_state: bool) -> None:
        """Baut den Kontext neu auf – für den Re-Login-Fallback."""
        self._stop_tracing()
        if self._context:
            self._context.close()
        self._build_context(with_state=with_state)
        log.info('Browser-Kontext neu aufgebaut (with_state=%s)', with_state)

    # ---------------------------------------------------------------- Zugriff

    @property
    def context(self):
        if self._context is None:
            raise RuntimeError('BrowserSession.start() wurde nicht aufgerufen')
        return self._context

    def new_page(self):
        """Frische Seite – verhindert Zustands-Bleeding zwischen Artikeln."""
        return self.context.new_page()

    # ---------------------------------------------------------------- State

    def save_state(self) -> Path:
        target = self.cfg.session_file
        if self.cfg.force_anonymous:
            log.debug('force_anonymous: Session wird nicht gespeichert')
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(target))
        try:
            target.chmod(0o600)          # enthält Session-Cookies = Credential
        except OSError:
            pass
        log.debug('Session gespeichert: %s', target)
        return target

    def clear_state(self) -> None:
        if self.cfg.session_file.exists():
            self.cfg.session_file.unlink()
            log.info('Gespeicherte Session verworfen')

    def cookies(self) -> list[dict]:
        return self.context.cookies()

    # ---------------------------------------------------------------- Ende

    def _stop_tracing(self) -> None:
        if self._tracing and self._context:
            try:
                self._context.tracing.stop(path=str(self.cfg.debug_dir / 'trace.zip'))
                log.info('Trace: %s', self.cfg.debug_dir / 'trace.zip')
            except Exception as e:
                log.warning('Trace konnte nicht geschrieben werden: %s', e)
            self._tracing = False

    def close(self) -> None:
        self._stop_tracing()
        for obj, name in ((self._context, 'Kontext'), (self._browser, 'Browser')):
            if obj:
                try:
                    obj.close()
                except Exception as e:
                    log.debug('%s schliessen fehlgeschlagen: %s', name, e)
        if self._pw:
            try:
                self._pw.stop()
            except Exception as e:
                log.debug('Playwright stoppen fehlgeschlagen: %s', e)
        self._context = self._browser = self._pw = None
        log.info('Browser-Session beendet', extra={'icon': '✓'})

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()
