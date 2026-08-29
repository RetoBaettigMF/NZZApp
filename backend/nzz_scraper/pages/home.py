"""Startseite www.nzz.ch – Einstieg für den Login."""
from __future__ import annotations

from ..logging_setup import get_logger
from ..models import PageType
from . import locators as L
from .base import BasePage

log = get_logger(__name__)


class HomePage(BasePage):
    page_type = PageType.HOME
    ready_selectors = L.HEADER
    default_url = L.SITE_ROOT

    def open_navigation(self) -> None:
        """Öffnet das Hamburger-Menü (mobil)."""
        self.first_visible('home.burger', L.BURGER_BUTTON).click()

    def account_indicator(self):
        """Selektor des Konto-Einstiegs, oder None."""
        return self.any_present(L.ACCOUNT_INDICATORS)

    def has_login_button(self) -> bool:
        return self.any_present(L.LOGIN_BUTTON) is not None

    def click_login(self):
        """Klickt Anmelden und liefert die PianoLoginPage.

        Mobil ist der Button direkt in der Kopfzeile – nicht hinter dem
        Hamburger (siehe MOBILE_SELECTORS.md).
        """
        from .login import PianoLoginPage

        self.dismiss_overlays()
        self.settle()
        self.first_visible('home.login', L.LOGIN_BUTTON).click()
        login = PianoLoginPage(self.page, self.ctx)
        login.wait_until_ready()
        return login
