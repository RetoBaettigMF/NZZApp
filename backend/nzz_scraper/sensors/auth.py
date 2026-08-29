"""LoginSensor – ist die Session eingeloggt?

Der alte Scraper prüfte 'Anmelden' in html and 'Abonnieren' in html und druckte
danach bedingungslos "authentifiziert". Hier zählen mehrere unabhängige Indizien;
für hohe Konfidenz (>= 0.7) müssen mindestens zwei davon feuern.
"""
from __future__ import annotations

from ..pages import locators as L
from .types import Signal, SensorResult, combine, unknown


class LoginSensor:
    name = 'login'

    def __init__(self, session=None):
        self.session = session          # BrowserSession, für context.cookies()

    def read(self, page, ctx) -> SensorResult:
        signals: list[Signal] = []

        # 1. Piano-Zustand – das belastbarste Einzelsignal.
        tp_valid = page.safe_eval(L.JS_TP_USER_VALID, default=None)
        tp_available = tp_valid is not None
        if tp_available:
            signals.append(Signal('piano_state', bool(tp_valid), 0.40,
                                  f'tp.user.isUserValid()={tp_valid}'))

        # 2. Session-Cookie
        if self.session is not None:
            try:
                names = [c['name'] for c in self.session.cookies()]
            except Exception:
                names = []
            hit = next((n for n in names
                        if any(n.startswith(h) or h in n for h in L.SESSION_COOKIE_HINTS)), None)
            signals.append(Signal('session_cookie', hit is not None, 0.25, hit or ''))

        # 3. Konto-Einstieg in der Kopfzeile
        account = page.any_present(L.ACCOUNT_INDICATORS)
        signals.append(Signal('account_ui', account is not None, 0.20, account or ''))

        # 4. Kein Anmelden-CTA mehr. Niedrig gewichtet: der Button kann auch
        #    aus anderen Gründen fehlen (andere Seitenvariante).
        login_cta = page.any_present(L.LOGIN_BUTTON)
        signals.append(Signal('no_login_cta', login_cta is None, 0.10, login_cta or ''))

        # 5. localStorage
        keys = page.safe_eval(L.JS_LOCAL_STORAGE_KEYS, default=[]) or []
        ls_hit = next((k for k in keys if 'piano' in k.lower() or 'user' in k.lower()), None)
        signals.append(Signal('local_storage', ls_hit is not None, 0.05, ls_hit or ''))

        if not signals:
            return unknown(self.name, 'kein Signal auswertbar')

        result = combine(self.name, signals, threshold=0.5)

        # Piano sagt explizit "nicht eingeloggt" -> das schlägt schwache Indizien.
        if tp_available and tp_valid is False and result.verdict:
            return SensorResult(self.name, False, 1.0 - result.confidence, result.signals,
                                'Piano meldet isUserValid()=false')
        return result
