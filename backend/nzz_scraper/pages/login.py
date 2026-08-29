"""Piano-ID-Login.

`frame` ist bewusst polymorph: eingebettetes iframe (heutiger Stand, mobil wie
Desktop) oder – falls NZZ das umstellt – die Seite selbst nach einem Redirect auf
id-eu.piano.io. Der Aufrufercode bleibt in beiden Fällen gleich.
"""
from __future__ import annotations

import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from ..errors import LoginFailedError, TransientScrapeError
from ..logging_setup import get_logger
from ..models import PageType
from . import locators as L
from .base import BasePage

log = get_logger(__name__)


class PianoLoginPage(BasePage):
    page_type = PageType.PIANO_LOGIN

    # --------------------------------------------------------------- Zustand

    def is_current(self) -> bool:
        if L.PIANO_URL.search(self.page.url):
            return True
        return self.any_present(L.PIANO_IFRAME) is not None

    @property
    def redirected(self) -> bool:
        """True, wenn NZZ auf eine Piano-Vollseite umgeleitet hat."""
        return bool(L.PIANO_URL.search(self.page.url))

    @property
    def frame(self):
        """FrameLocator (iframe) oder die Page selbst (Redirect)."""
        if self.redirected:
            return self.page
        for selector in L.PIANO_IFRAME:
            if self.page.locator(selector).count():
                return self.page.frame_locator(selector)
        raise TransientScrapeError('Piano-Login weder als iframe noch als Redirect gefunden')

    def wait_for_form_host(self, timeout_ms: int = 15_000) -> None:
        """Wartet, bis das Piano-Formular überhaupt existiert.

        Nach dem Klick auf "Anmelden" dauert es einen Moment, bis das iframe im
        DOM steht. Wer sofort auf frame_locator zugreift, bekommt "weder iframe
        noch Redirect" – ein Timing-Fehler, der wie ein Strukturbruch aussieht.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.redirected or any(self.page.locator(sel).count()
                                      for sel in L.PIANO_IFRAME):
                return
            self.page.wait_for_timeout(250)
        self.capture_debug('piano-host-missing')
        raise TransientScrapeError(
            f'Piano-Login erschien nicht innert {timeout_ms}ms nach dem Klick')

    def wait_until_ready(self, timeout_ms: int | None = None):
        """Wartet, bis das Eingabefeld für die E-Mail sichtbar ist."""
        timeout_ms = timeout_ms or 20_000
        self.wait_for_form_host()
        try:
            field = self._field(L.PIANO_EMAIL)
            expect(field).to_be_visible(timeout=timeout_ms)
            expect(field).to_be_editable(timeout=5_000)
        except (AssertionError, PlaywrightTimeoutError, PlaywrightError) as e:
            self.capture_debug('piano-not-ready', error=e)
            raise TransientScrapeError(f'Piano-Login-Formular nicht erschienen: {e}') from e
        return self

    # --------------------------------------------------------------- Aktionen

    def _field(self, selectors):
        frame = self.frame
        for selector in selectors:
            loc = frame.locator(selector).first
            try:
                if loc.count():
                    return loc
            except PlaywrightError:
                continue
        return frame.locator(selectors[0]).first

    def has_captcha(self) -> bool:
        """reCAPTCHA im Piano-Frame – dann hilft nur ein manueller Lauf."""
        for selector in L.CAPTCHA:
            try:
                if self.page.locator(selector).first.is_visible(timeout=250):
                    return True
            except PlaywrightError:
                continue
        return False

    def error_message(self) -> str | None:
        """Unterscheidet 'Passwort falsch' von 'Netzwerkfehler'.

        Liefert None, wenn das Formular gar nicht (mehr) da ist – dieser Aufruf
        passiert typischerweise in Fehlerpfaden und darf nicht selbst werfen.
        """
        try:
            frame = self.frame
        except TransientScrapeError:
            return None
        for selector in L.PIANO_ERROR:
            try:
                loc = frame.locator(selector).first
                if loc.is_visible(timeout=400):
                    text = loc.inner_text().strip()
                    if text:
                        return text
            except PlaywrightError:
                continue
        return None

    def _fill_secret(self, locator, value: str, what: str, *, attempts: int = 3) -> None:
        """Füllt ein Feld und prüft, dass der Wert auch stehen bleibt.

        Zwei Gründe für die Umständlichkeit:

        * Piano rendert das Formular nach, nachdem es sichtbar wurde. Ein zu
          früher fill() wird dabei wieder verworfen – das Feld ist dann leer,
          "Weiter" tut nichts, und der Fehler zeigt sich erst zwei Schritte
          später als "Passwortfeld erschien nicht".
        * Playwright hängt bei einem Timeout das komplette Call-Log an die
          Exception – inklusive fill("<passwort>"). Der Wert wird deshalb aus
          jeder Fehlermeldung entfernt.
        """
        for attempt in range(1, attempts + 1):
            try:
                locator.fill(value)
                if locator.input_value() == value:
                    return
                log.debug('%s war nach dem Befüllen leer (Versuch %d) – erneut',
                          what, attempt)
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                scrubbed = str(e).replace(value, '***') if value else str(e)
                if attempt >= attempts:
                    raise TransientScrapeError(
                        f'{what} konnte nicht ausgefüllt werden: '
                        f'{scrubbed.splitlines()[0]}') from None
                log.debug('%s: Versuch %d fehlgeschlagen', what, attempt)
            self.page.wait_for_timeout(600)

        raise TransientScrapeError(f'{what} liess sich nicht befüllen (Wert ging verloren)')

    def submit(self, email: str, password: str) -> None:
        """Füllt das zweistufige Formular ab.

        Piano fragt mobil zuerst nur die E-Mail ab ("Weiter"); das Passwortfeld
        existiert bereits im DOM, ist aber unsichtbar. Erst nach dem ersten
        Schritt wird es eingeblendet ("Anmelden").
        """
        self._fill_secret(self._field(L.PIANO_EMAIL), email, 'E-Mail-Feld')

        password_field = self._field(L.PIANO_PASSWORD)
        if not self._is_visible(password_field):
            self._advance_to_password(password_field)

        self._fill_secret(password_field, password, 'Passwortfeld')
        self._activate_submit(L.PIANO_PASSWORD, prefer_enter=True)

    def _activate_submit(self, field_selectors, *, prefer_enter: bool = True) -> None:
        """Schickt das Formular ab.

        Enter im fokussierten Feld statt Klick auf den Button: das Piano-Modal ist
        703px hoch in einem iframe mit scrolling="no", der Absenden-Button liegt
        damit je nach Layout ausserhalb des klickbaren Bereichs. Playwright hält
        ihn trotzdem für sichtbar – der Klick verpufft dann folgenlos.
        """
        if prefer_enter:
            try:
                self._field(field_selectors).press('Enter')
                return
            except PlaywrightError as e:
                log.debug('Enter fehlgeschlagen, versuche Klick: %s', e)
        self._field(L.PIANO_SUBMIT).click()

    def _advance_to_password(self, password_field, *, attempts: int = 2) -> None:
        """Bestätigt den E-Mail-Schritt, bis das Passwortfeld sichtbar ist.

        Der erste Klick geht gelegentlich ins Leere, wenn Piano seine Handler
        noch nicht gebunden hat. Zweiter Versuch: Enter im E-Mail-Feld.
        """
        log.debug('Zweistufiges Formular – bestätige E-Mail-Schritt')
        for attempt in range(1, attempts + 1):
            try:
                self._activate_submit(L.PIANO_EMAIL, prefer_enter=(attempt == 1))
            except PlaywrightError as e:
                log.debug('E-Mail-Schritt, Versuch %d: %s', attempt, e)

            try:
                expect(password_field).to_be_visible(timeout=8_000)
                return
            except (AssertionError, PlaywrightTimeoutError, PlaywrightError):
                err = self.error_message()
                if err:
                    # Fachlicher Fehler (unbekannte Adresse) – Wiederholen bringt nichts.
                    self.capture_debug('piano-step1-error')
                    raise LoginFailedError(f'Piano lehnt die E-Mail-Adresse ab: {err}')
                log.debug('Passwortfeld nach Versuch %d noch nicht sichtbar', attempt)

        self.capture_debug('piano-step2-missing')
        raise TransientScrapeError('Passwortfeld erschien nicht nach dem E-Mail-Schritt')

    @staticmethod
    def _is_visible(locator) -> bool:
        try:
            return locator.is_visible(timeout=1000)
        except PlaywrightError:
            return False

    def wait_until_closed(self, timeout_ms: int = 25_000) -> bool:
        """Wartet, bis das Piano-iframe verschwindet. False bei Timeout."""
        if self.redirected:
            try:
                self.page.wait_for_url(
                    lambda u: not L.PIANO_URL.search(u), timeout=timeout_ms)
                return True
            except PlaywrightTimeoutError:
                return False
        try:
            expect(self.page.locator(L.PIANO_IFRAME[0])).to_have_count(0, timeout=timeout_ms)
            return True
        except (AssertionError, PlaywrightTimeoutError, PlaywrightError):
            return False
