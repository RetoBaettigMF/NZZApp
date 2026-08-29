"""ProSensor – ist das ein NZZ-Pro-Artikel?

NZZ hat zwei Abostufen. Wer die kleinere hat, kommt an Pro-Artikel nicht heran;
sie würden bei jedem Lauf erneut geholt, als Paywall erkannt und verworfen –
und weil Paywall-Artikel bewusst nicht getrackt werden, ginge das endlos so
weiter. Deshalb werden sie separat erkannt und übersprungen.

Der Marker ist strukturiert und serverseitig gerendert, also sofort verfügbar:
<meta name="mrf:tags" content="...;Content Type:Pro Article;...">
"""
from __future__ import annotations

from ..pages import locators as L
from .types import Signal, SensorResult, combine, unknown


class ProSensor:
    name = 'pro_article'

    def content_type(self, page) -> str | None:
        """'Pro Article', 'Standard Article' – oder None, wenn nicht auslesbar."""
        return page.safe_eval(L.JS_CONTENT_TYPE, default=None)

    def read(self, page, ctx) -> SensorResult:
        content_type = self.content_type(page)
        if content_type is None:
            # Ohne das Meta-Tag lässt sich nichts sagen. Bewusst None statt
            # False: "weiss nicht" darf nicht als "kein Pro-Artikel" gelten.
            return unknown(self.name, 'meta mrf:tags nicht vorhanden')

        is_pro = content_type == L.CONTENT_TYPE_PRO
        signals = [Signal('meta_content_type', is_pro, 1.0, content_type)]
        return combine(self.name, signals, threshold=0.5,
                       reason=f'Content Type: {content_type}',
                       extra={'content_type': content_type})
