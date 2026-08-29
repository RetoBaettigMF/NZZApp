# Mobile NZZ-Selektoren – Ermittlungsprotokoll

**Ermittelt am:** 2026-08-29
**Profil:** Playwright `devices['Pixel 7']` (Chromium, 412×839, `is_mobile`, `has_touch`),
`locale='de-CH'`, `timezone_id='Europe/Zurich'`
**Werkzeug:**

```bash
backend/venv/bin/python -m nzz_scraper.tools.explore --url https://www.nzz.ch
backend/venv/bin/python -m nzz_scraper.tools.explore --url <artikel-url>
backend/venv/bin/python -m nzz_scraper.tools.explore --url https://www.nzz.ch/neueste-artikel --scroll
```

Zum Wiederholen nach einem NZZ-Redesign: obige Kommandos laufen lassen und
`candidates.json` im Ausgabeverzeichnis auswerten.

---

## Grundsätzliches

NZZ nutzt **Tailwind-Utility-Klassen** (`bg-gradient-to-r from-lavender-mist …`).
Es gibt **kein einziges `data-testid`** auf der Site. Klassennamen sind damit als
Selektor weitgehend wertlos – tragfähig sind:

1. **ARIA / Accessible Name** (`aria-label`, `role`) – die Site ist gut ausgezeichnet
2. **Semantische Marker-Klassen**, die kein Tailwind sind: `container--article`, `article`
3. **Struktur** (`h1`, `time[datetime]`, `section > p`)

## Beantwortete Fragen

| # | Frage | Befund |
|---|---|---|
| 1 | „Anmelden" hinter dem Hamburger? | **Nein.** `button[aria-label="Anmelden"]` ist mobil direkt in der Kopfzeile sichtbar. Der Hamburger ist separat: `button[aria-label="Menü öffnen"]`. |
| 2 | Eigene mobile Origin? | **Nein.** Gleiche Origin `www.nzz.ch`, responsives DOM, `<meta name=viewport content="width=device-width, initial-scale=1">`. |
| 3 | Piano: iframe oder Redirect? | **Eingebettetes iframe**, wie auf dem Desktop: `iframe[src*="id-eu.piano.io"]`, Frame-Name `piano-id-<zufall>`. `input[name=email]` und `input[type=password]` liegen zusammen im selben Frame (einstufiges Formular). Im Frame läuft zusätzlich ein **reCAPTCHA**. |
| 4 | Artikel-Fliesstext? | **`section.container--article`**. Siehe Warnung unten. |
| 5 | `/neueste-artikel` mobil? | **Ja**, mit Infinite Scroll. 17 Links initial, wächst über ~11 Scrollrunden auf ~168. Kein „Mehr anzeigen"-Button. |
| 6 | Login-Nachweis? | **`window.tp.user.isUserValid()`** – liefert anonym `false`. Bestes Einzelsignal. |
| 7 | Consent mobil? | `div#cmpbox[role="dialog"]`, Zustimmen via **`#cmpwelcomebtnyes`** – identisch zum Desktop, **kein** iframe. |

---

## ⚠ Zwei Befunde, die das Design bestimmen

### A) `article` ist eine Falle

Die alte Selektorkaskade begann mit `'article'` und nahm den ersten Treffer mit
>200 Zeichen. Auf einer mobilen Artikelseite misst:

| Selektor | Zeichen | `<p>` |
|---|---|---|
| `section.container--article` | **6589** | **23** |
| `div.article` | 9717 (inkl. Empfehlungen) | 23 |
| `article` (HTML-Tag) | **320** | 1 |
| `main` | existiert nicht | – |

`article` liefert 320 Zeichen – über der 200er-Schwelle, also hätte die alte
Kaskade dort gestoppt. Das erklärt die chronisch kurzen Artikel.
Auf der **Startseite** ist zudem jeder Teaser ein `<article>`.

### B) Die Paywall greift clientseitig, ~2 Sekunden nach dem Laden

Gemessen an einem Pro-Artikel, anonym:

```
t+1.6s   23 <p>   6078 Zeichen      ← serverseitig gerendert, vollständig
t+2.8s    7 <p>    757 Zeichen      ← Piano ersetzt den Inhalt
t+17s     7 <p>    757 Zeichen      ← stabil
```

Konsequenzen:

* **Es darf nicht sofort extrahiert werden.** Wer direkt nach `domcontentloaded`
  liest, greift den Text vor dem Zugriffsentscheid ab. Der Scraper wartet
  deshalb auf DOM-Stabilität (`wait_for_stable_content`) und extrahiert erst danach.
* Ein Lauf ohne gültigen Login liefert damit *sichtbar* Anrisse, statt still
  Volltexte einzusammeln – genau das soll der PaywallSensor melden, damit der
  Artikel übersprungen und beim nächsten Lauf erneut versucht wird.
* Längeres Warten macht die Ausbeute anonym *schlechter*, nicht besser.

Im gekürzten Zustand gibt es **keine** Paywall-Klassennamen. Erkennbar ist er an
einem sichtbaren **„NZZ abonnieren"**-Button und daran, dass der Text mitten im
Satz endet.

### C) Zwei Abostufen – NZZ Pro ist sauber ausgezeichnet

NZZ verkauft ein Standard-Abo und ein teureres mit NZZ-Pro-Artikeln. Piano gibt
die Stufe nicht her (`window.tp.user.getUser()` liefert `null`), aber der
Artikeltyp steht strukturiert im Kopf der Seite:

```html
<meta name="mrf:tags" content="Page Type:regular;Editorial Owner:NZZ;
                               Content Type:Pro Article;Article ID:ld.10021479">
```

Werte: `Pro Article` bzw. `Standard Article`. Serverseitig gerendert, also
sofort verfügbar – kein Warten auf Piano nötig.

Im Feed trägt der Teaser-Kasten zusätzlich das sichtbare Label **„Pro Artikel"**.
Gegenprobe an acht Artikeln: **8/8 Übereinstimmung** zwischen Teaser-Label und
Meta-Tag. Damit lassen sich Pro-Artikel überspringen, *ohne sie zu laden*.

Zwei Fallstricke:

* Im ganzen Seitentext nach „Pro Artikel" zu suchen erzeugt Fehltreffer –
  auch Standard-Artikel blenden Pro-Beiträge als Empfehlung ein. Die Prüfung
  muss auf den Teaser-Kasten des jeweiligen Links begrenzt bleiben
  (`a.closest('article')`).
* `span.sr-only` mit dem Text „Pro Artikel" steht aus demselben Grund ebenfalls
  auf freien Artikeln. Nicht als Marker verwenden.

Die Abostufe selbst wird empirisch ermittelt: der erste Pro-Artikel eines Laufs
wird geholt; kürzt Piano ihn, fehlt das Pro-Abo. Ergebnis landet in
`backend/.state/nzz_entitlement.json` und wird nach sieben Tagen neu geprüft,
damit ein Upgrade nicht dauerhaft unbemerkt bleibt.

---

## Weitere Beobachtungen

* Die alte Link-Regex `^/[\w-]+/[\w-]+\.\d+$` trifft auch
  `/information/impressum-ld.148422`. `/information/` wird deshalb ausgeschlossen.
* Artikel-IDs haben die Form `…-ld.10021602`.
* Seitentyp-Signale sind zuverlässig: `<meta property="og:type">` ist
  `article` bzw. `website`, und Artikel tragen JSON-LD `"@type": "NewsArticle"`.
* Der Feed wächst nicht monoton – einzelne Scrollrunden liefern nichts, die
  nächste wieder 16 Links. `stall_rounds` muss darum > 2 sein.
