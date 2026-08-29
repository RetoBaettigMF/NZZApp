"""Login-Verwaltung mit Session-Persistenz und Re-Login-Fallback.

Ablauf: gespeicherte Session laden -> LoginSensor fragen -> nur bei negativem
Verdikt den vollen Piano-Flow fahren. Ein fehlgeschlagener Login bricht den Lauf
ab (Exit 2); der alte Scraper degradierte hier still auf anonymes Scraping.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from ..browser import BrowserSession
from ..config import ScraperConfig
from ..debug import DebugArtifacts
from ..errors import LoginFailedError, TransientScrapeError
from ..logging_setup import get_logger
from ..pages.base import PageContext
from ..retry import with_retry
from ..pages.home import HomePage
from ..sensors.auth import LoginSensor
from ..sensors.types import SensorResult

log = get_logger(__name__)

# Für "eingeloggt" verlangen wir zwei unabhängige Signale.
CONFIDENT = 0.6


@dataclass
class LoginState:
    logged_in: bool
    via: Literal['storage_state', 'piano', 'anonymous']
    sensor: SensorResult


class AuthManager:
    def __init__(self, session: BrowserSession, cfg: ScraperConfig,
                 debug: DebugArtifacts, ctx: PageContext):
        self.session = session
        self.cfg = cfg
        self.debug = debug
        self.ctx = ctx
        self.sensor = LoginSensor(session)
        self._relogins = 0

    @property
    def relogin_attempts(self) -> int:
        return self._relogins

    # ------------------------------------------------------------------ API

    def check(self, page) -> SensorResult:
        """Liest den LoginSensor auf einer beliebigen bereits geladenen Seite."""
        home = HomePage(page, self.ctx)
        return self.sensor.read(home, self.ctx)

    def ensure_logged_in(self, page, *, force: bool = False) -> LoginState:
        """Stellt sicher, dass die Session eingeloggt ist."""
        if self.cfg.force_anonymous:
            log.warning('force_anonymous: Login wird übersprungen')
            return LoginState(False, 'anonymous', self.check(page))
        if not force:
            state = self._verify(page)
            if state.logged_in:
                return state

        if not (self.cfg.email and self.cfg.password):
            if self.cfg.allow_anonymous:
                log.warning('Keine Credentials – Lauf bleibt anonym')
                return LoginState(False, 'anonymous', self.check(page))
            raise LoginFailedError('NZZ_EMAIL/NZZ_PASSWORD fehlen')

        # Der Piano-Flow ist der fragilste Teil; TransientScrapeError wird
        # wiederholt, LoginFailedError (falsche Credentials) nicht.
        return with_retry(
            lambda: self._perform_login(page),
            attempts=2, base_delay=3.0,
            retry_on=(TransientScrapeError,),
            on_retry=lambda n, e: log.warning('Login-Versuch %d gescheitert: %s', n, e))

    def relogin(self, page) -> LoginState:
        """Verwirft die gespeicherte Session und loggt neu ein."""
        if self.cfg.force_anonymous:
            raise LoginFailedError('Re-Login angefordert, aber force_anonymous ist gesetzt')
        self._relogins += 1
        if self._relogins > self.cfg.max_relogins:
            raise LoginFailedError(
                f'Mehr als {self.cfg.max_relogins} Re-Logins – Abbruch')

        log.warning('Re-Login %d/%d', self._relogins, self.cfg.max_relogins)
        self.session.clear_state()
        self.session.reload_context(with_state=False)
        new_page = self.session.new_page()
        state = self._perform_login(new_page)
        return state

    # ------------------------------------------------------------------ intern

    def _verify(self, page) -> LoginState:
        home = HomePage(page, self.ctx)
        if not page.url.startswith(self.cfg.site_root):
            home.open()
        home.dismiss_overlays()

        # Pollen statt einmal schauen: window.tp meldet den Anmeldezustand erst
        # nach rund zwei Sekunden. Ein einzelner Blick würde "ausgeloggt" sagen
        # und bei jedem Lauf einen überflüssigen Piano-Durchlauf auslösen.
        result = self._poll_sensor(page, timeout_s=8.0)
        if result.at_least(CONFIDENT):
            log.info('Bereits eingeloggt (Konfidenz %.2f, %d Signale): %s',
                     result.confidence, len(result.positive()), result.reason,
                     extra={'icon': '✓'})
            return LoginState(True, 'storage_state', result)

        log.info('Nicht eingeloggt: %s', result.describe())
        return LoginState(False, 'storage_state', result)

    def _perform_login(self, page) -> LoginState:
        home = HomePage(page, self.ctx)
        home.open().wait_until_ready()
        home.dismiss_overlays()

        # Beim zweiten Anlauf kann der erste bereits erfolgreich gewesen sein –
        # dann gibt es keinen Anmelden-Button mehr, und ein blinder Klickversuch
        # würde an der Selektorkette scheitern.
        already = self.sensor.read(home, self.ctx)
        if already.at_least(CONFIDENT):
            log.info('Bereits eingeloggt (Konfidenz %.2f)', already.confidence,
                     extra={'icon': '✓'})
            self.session.save_state()
            # Kein Piano-Formular angefasst – der Weg war die gespeicherte Session.
            return LoginState(True, 'storage_state', already)

        log.info('Starte Piano-Login für %s', self.cfg.email)
        login = home.click_login()

        if login.has_captcha():
            self.debug.capture(page, 'login-captcha')
            log.warning('reCAPTCHA im Login-Formular sichtbar – '
                        'ein headed Lauf (--headed) kann nötig sein')

        login.submit(self.cfg.email, self.cfg.password)

        # Ob das iframe verschwindet, ist nur ein Indiz. Massgeblich ist der
        # Sensor – sonst scheitert ein erfolgreicher Login daran, dass Piano das
        # Modal anders schliesst als erwartet.
        closed = login.wait_until_closed()
        if not closed:
            log.debug('Piano-Modal blieb sichtbar – prüfe trotzdem den Sensor')

        # Neu laden statt zu schlafen: die Kopfzeile rendert den Konto-Einstieg
        # erst bei der nächsten Navigation, und der Reload belegt zugleich, dass
        # die Session eine Navigation überlebt.
        try:
            home.open().wait_until_ready()
            home.dismiss_overlays()
        except TransientScrapeError as e:
            log.debug('Reload nach Login übersprungen: %s', e)
        result = self._poll_sensor(page)
        if not result.at_least(CONFIDENT):
            err = login.error_message()
            self.debug.capture(page, 'login-unverified', sensors=[result],
                               extra={'piano_error': err, 'modal_closed': closed})
            if err:
                # Fachliche Ablehnung (falsches Passwort) – Wiederholen zwecklos.
                raise LoginFailedError(f'Piano meldet: {err}')
            raise LoginFailedError(f'Login nicht verifizierbar: {result.describe()}')

        log.info('Login erfolgreich (Konfidenz %.2f, %d Signale)',
                 result.confidence, len(result.positive()), extra={'icon': '✓'})
        self.session.save_state()
        return LoginState(True, 'piano', result)

    def _poll_sensor(self, page, timeout_s: float = 20.0) -> SensorResult:
        """Pollt den LoginSensor, statt eine feste Zeit zu schlafen.

        Bricht früh ab, sobald Piano ein eindeutiges Urteil gefällt hat – ein
        klares "nicht eingeloggt" muss nicht ausgesessen werden.
        """
        home = HomePage(page, self.ctx)
        deadline = time.monotonic() + timeout_s
        result = self.sensor.read(home, self.ctx)
        while time.monotonic() < deadline and not result.at_least(CONFIDENT):
            if self._decided_negative(result):
                break
            page.wait_for_timeout(500)
            result = self.sensor.read(home, self.ctx)
        return result

    @staticmethod
    def _decided_negative(result: SensorResult) -> bool:
        """Piano hat geantwortet und sagt: nicht angemeldet."""
        return any(s.name == 'piano_state' and not s.fired and 'False' in s.detail
                   for s in result.signals)
