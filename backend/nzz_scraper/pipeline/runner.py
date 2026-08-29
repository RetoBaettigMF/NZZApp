"""Ablaufsteuerung eines Scraper-Laufs."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from ..browser import BrowserSession
from ..config import ScraperConfig
from ..debug import DebugArtifacts
from ..errors import (EXIT_BLOCKED, EXIT_FAILED, EXIT_LOGIN, EXIT_OK, BlockedError,
                      LoginFailedError, PaywallError, TransientScrapeError,
                      UnexpectedPageError)
from ..extraction.category import extract_category
from ..extraction.markdown import html_fragment_to_markdown
from ..logging_setup import get_logger
from ..models import Article, RunResult
from ..pages.article import ArticlePage
from ..pages.base import PageContext
from ..pages.feed import LatestArticlesPage
from ..retry import with_retry
from ..sensors import (BlockingSensor, ContentQualitySensor, PageTypeSensor,
                       PaywallSensor, ProSensor)
from .auth_manager import AuthManager
from .entitlement import EntitlementStore
from .output import ArticleWriter, create_zip, update_manifest
from .tracking import TrackingStore

log = get_logger(__name__)

BLOCK_BACKOFF_S = (60, 300, 900)


class ScraperRun:
    """Ein Lauf: einloggen, Links holen, neue Artikel scrapen, schreiben."""

    def __init__(self, cfg: ScraperConfig):
        self.cfg = cfg
        self.debug = DebugArtifacts(cfg.debug_dir)
        self.ctx = PageContext(cfg=cfg, debug=self.debug,
                               page_type_sensor=PageTypeSensor())
        self.tracking = TrackingStore(cfg.tracking_file)
        self.writer = ArticleWriter(cfg.output_dir)
        self.paywall = PaywallSensor()
        self.pro = ProSensor()
        self.entitlement = EntitlementStore(cfg.entitlement_file, cfg.pro_recheck_days)
        self.quality = ContentQualitySensor()
        self.blocking = BlockingSensor()
        self.result = RunResult()
        self._ai = None
        self._ai_failed = False
        self._blocks = 0
        self._has_pro: bool | None = None

    # ------------------------------------------------------------------ AI

    @property
    def ai(self):
        """OpenRouter-Client, einmalig und träge. None, wenn nicht verfügbar."""
        if self._ai is None and not self._ai_failed and self.cfg.use_ai:
            try:
                from openrouter_client import OpenRouterClient
                self._ai = OpenRouterClient()
                log.info('OpenRouter-Client initialisiert', extra={'icon': '✓'})
            except (ImportError, ValueError) as e:
                log.warning('OpenRouter nicht verfügbar: %s', e)
                self._ai_failed = True
        return self._ai

    # ------------------------------------------------------------------ Lauf

    def execute(self, *, limit: int | None = None, dry_run: bool = False) -> RunResult:
        started = time.monotonic()
        deadline = started + self.cfg.run_budget_s
        self.cfg.ensure_dirs()
        self.tracking.load()

        session = BrowserSession(self.cfg)
        try:
            session.start()
            auth = AuthManager(session, self.cfg, self.debug, self.ctx)
            page = session.new_page()
            state = auth.ensure_logged_in(page)
            if not state.logged_in and not (self.cfg.allow_anonymous or self.cfg.force_anonymous):
                raise LoginFailedError('Login konnte nicht verifiziert werden')

            self._load_entitlement()

            entries = self._collect_links(page)
            self.result.links_found = len(entries)

            fresh = [e for e in entries if not self.tracking.is_scraped(e.url)]
            fresh = self._drop_unreachable_pro(fresh)
            # Standard-Artikel zuerst: sie liefern die Vergleichslänge, an der
            # sich erkennen lässt, ob ein Pro-Artikel nur ein Anriss ist.
            fresh.sort(key=lambda e: e.is_pro)
            total_new = len(fresh)
            if limit:
                fresh = fresh[:limit]
            fresh = self._ensure_pro_probe(fresh, entries)
            new_links = [e.url for e in fresh]
            self.result.new_links = len(new_links)
            log.info('%d Links gefunden, %d neu%s', len(entries), total_new,
                     f' (auf {limit} begrenzt)' if limit else '')

            if not new_links:
                log.info('Keine neuen Artikel', extra={'icon': '✓'})
                return self._finish(started, EXIT_OK)

            today = datetime.now().strftime('%Y-%m-%d')
            date_folder = self.cfg.output_dir / today
            date_folder.mkdir(parents=True, exist_ok=True)

            articles = self._scrape_all(session, auth, new_links, deadline)
            self.result.relogins = auth.relogin_attempts

            if dry_run:
                log.warning('--dry-run: %d Artikel werden nicht geschrieben', len(articles))
                return self._finish(started, EXIT_OK)

            self._write(articles, date_folder, today)
            return self._finish(started, self._exit_code())

        except LoginFailedError as e:
            log.critical('Login fehlgeschlagen: %s', e)
            return self._finish(started, EXIT_LOGIN)
        except BlockedError as e:
            log.critical('Von NZZ blockiert: %s', e)
            return self._finish(started, EXIT_BLOCKED)
        finally:
            session.close()

    # ------------------------------------------------------------------ Teile

    def _collect_links(self, page):
        feed = LatestArticlesPage(page, self.ctx)
        feed.open(self.cfg.base_url).assert_ready()
        feed.dismiss_overlays()
        self._check_blocked(feed)
        return feed.collect_entries(max_links=self.cfg.max_links)

    def _load_entitlement(self) -> None:
        """Legt fest, ob NZZ-Pro-Artikel überhaupt erreichbar sind."""
        if self.cfg.pro_access in ('yes', 'no'):
            self._has_pro = self.cfg.pro_access == 'yes'
            log.info('Pro-Zugriff per Konfiguration: %s',
                     'ja' if self._has_pro else 'nein')
            return

        state = self.entitlement.load()
        if self.entitlement.needs_probe:
            # Der erste Pro-Artikel des Laufs dient als Stichprobe. Das gilt
            # auch für eine fällige Wiederholung, damit ein Abo-Upgrade
            # irgendwann auffällt.
            self._has_pro = None
            if state.has_pro is None:
                log.info('Pro-Zugriff noch unbekannt – wird am ersten Pro-Artikel geprüft')
            else:
                log.info('Pro-Zugriff wird neu geprüft (letzte Prüfung älter als %d Tage)',
                         self.cfg.pro_recheck_days)
        else:
            self._has_pro = state.has_pro
            log.info('%s', state.describe())

    def _drop_unreachable_pro(self, entries):
        """Filtert Pro-Artikel heraus, wenn das Abo sie nicht abdeckt.

        Das passiert vor dem Laden: die Teaser-Markierung im Feed genügt, die
        Seite muss gar nicht erst geholt werden. Übersprungene Pro-Artikel
        werden bewusst NICHT getrackt – nach einem Abo-Upgrade sollen sie
        wieder eingesammelt werden.
        """
        if self._has_pro is not False:
            return entries

        keep = [e for e in entries if not e.is_pro]
        skipped = len(entries) - len(keep)
        if skipped:
            self.result.skipped_pro += skipped
            log.info('%d NZZ-Pro-Artikel übersprungen (Abo deckt sie nicht ab)', skipped)
        return keep

    def _ensure_pro_probe(self, batch, entries):
        """Hängt einen Pro-Artikel an, wenn die Abo-Stufe noch offen ist.

        Ohne das käme die Stichprobe nie zustande: Standard-Artikel stehen
        vorne, und ein --limit schneidet die Pro-Artikel weg.
        """
        if self._has_pro is not None or not batch or not entries:
            return batch
        if any(e.is_pro for e in batch):
            return batch
        known = {e.url for e in batch}
        probe = next((e for e in entries
                      if e.is_pro and e.url not in known
                      and not self.tracking.is_scraped(e.url)), None)
        if probe is None:
            return batch
        log.info('Hänge einen Pro-Artikel als Stichprobe an: %s', probe.url)
        return batch + [probe]

    # Ein Pro-Anriss misst rund ein Zehntel eines vollen Artikels
    # (gemessen: 722 und 1271 Zeichen gegenüber 7107).
    PRO_STUB_RATIO = 0.4
    PRO_PROBE_MIN_SAMPLES = 3

    def _probe_pro_access(self, chars: int) -> bool | None:
        """Ermittelt an einem Pro-Artikel, ob das Abo ihn abdeckt.

        Der PaywallSensor hilft hier nicht: Pro-Artikel werden bereits
        serverseitig gekürzt ausgeliefert, der Container schrumpft also nicht.
        Verlässlich ist der Längenvergleich mit den Standard-Artikeln desselben
        Laufs.
        """
        median = self.paywall.median
        if median is None:
            log.info('  Pro-Stichprobe verschoben: erst %d/%d Standard-Artikel als '
                     'Vergleich', self.paywall.samples, self.PRO_PROBE_MIN_SAMPLES)
            return None

        has_pro = chars >= self.PRO_STUB_RATIO * median
        log.info('  Pro-Stichprobe: %d Zeichen gegenüber Median %.0f → Pro-Abo %s',
                 chars, median, 'vorhanden' if has_pro else 'nicht vorhanden')
        self._has_pro = has_pro
        self.entitlement.set(has_pro)
        return has_pro

    def _scrape_all(self, session, auth, links: list[str], deadline: float) -> list[Article]:
        articles: list[Article] = []
        total = len(links)

        for index, url in enumerate(links, 1):
            if time.monotonic() >= deadline:
                msg = f'Laufbudget erschöpft nach {index - 1}/{total} Artikeln'
                log.warning(msg)
                self.result.notes.append(msg)
                break

            log.info('[%d/%d] %s', index, total, url)
            article = self._scrape_one_guarded(session, auth, url, deadline)
            if article:
                articles.append(article)
                self.result.scraped += 1

        return articles

    def _scrape_one_guarded(self, session, auth, url: str, deadline: float):
        budget = min(time.monotonic() + self.cfg.article_budget_s, deadline)
        page = session.new_page()
        try:
            return with_retry(
                lambda: self._scrape_one(session, auth, page, url),
                attempts=3, base_delay=2.0, deadline=budget,
                retry_on=(TransientScrapeError,),
                on_retry=lambda n, e: log.warning('  Retry %d/3: %s', n, e))
        except PaywallError as e:
            # Nicht speichern, nicht tracken -> beim nächsten Lauf erneut versuchen.
            self.result.skipped_paywalled += 1
            log.warning('  Übersprungen (Paywall): %s', e)
            return None
        except UnexpectedPageError as e:
            self.result.failed += 1
            log.error('  Übersprungen (falscher Seitentyp): %s', e)
            return None
        except TransientScrapeError as e:
            self.result.failed += 1
            log.error('  Endgültig fehlgeschlagen: %s', e)
            self.debug.capture(page, 'article-failed', error=e)
            return None
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _scrape_one(self, session, auth, page, url: str) -> Article | None:
        article_page = ArticlePage(page, self.ctx)
        article_page.open(url).assert_ready()
        self._check_blocked(article_page)
        article_page.dismiss_overlays()

        # Sicherheitsnetz: die Teaser-Markierung im Feed kann fehlen, das
        # Meta-Tag auf der Artikelseite ist massgeblich.
        pro = self.pro.read(article_page, self.ctx)
        if pro.verdict and self._has_pro is False:
            self.result.skipped_pro += 1
            log.info('  Übersprungen (NZZ Pro, Abo deckt es nicht ab)')
            return None

        raw = article_page.extract()
        markdown = html_fragment_to_markdown(raw.html)

        if pro.verdict and self._has_pro is None:
            # Erster Pro-Artikel des Laufs: Stichprobe für die Abo-Stufe.
            if self._probe_pro_access(len(markdown)) is not True:
                self.result.skipped_pro += 1
                return None

        paywall = self.paywall.read(article_page, self.ctx, raw=raw, content_chars=len(markdown))
        if paywall.verdict:
            # Paywall trotz Abo heisst meistens: die Session ist abgelaufen.
            # Einmal neu einloggen und den Artikel wiederholen – aber nur, wenn
            # überhaupt eingeloggt werden soll.
            if not self.cfg.force_anonymous and not auth.check(page).at_least(0.6):
                log.warning('  Paywall + ausgeloggt -> Re-Login')
                auth.relogin(page)
                raise TransientScrapeError('Session war abgelaufen, Artikel erneut versuchen')
            raise PaywallError(url, paywall.confidence)

        quality = self.quality.read(raw, markdown, page_title=page.title())
        if not quality.verdict:
            self.result.skipped_quality += 1
            log.warning('  Übersprungen (Qualität): %s', quality.describe())
            self.debug.capture(page, 'low-quality', sensors=[quality, paywall])
            return None

        # Nur Standard-Artikel bilden die Vergleichslänge – ein Pro-Anriss
        # würde den Median nach unten ziehen und die Stichprobe verfälschen.
        if not pro.verdict:
            self.paywall.note_length(len(markdown))
        return self._build_article(raw, markdown)

    def _build_article(self, raw, markdown: str) -> Article:
        summary, ai_cleaned = '', False
        if self.ai:
            cleaned = self.ai.clean_article_content(markdown, raw.title)
            if cleaned:
                markdown, ai_cleaned = cleaned, True
                log.debug('  AI-Bereinigung: %d Zeichen', len(markdown))
            summary = self.ai.generate_summary(markdown, raw.title) or ''

        return Article(
            title=raw.title,
            url=raw.url,
            date=raw.published_at,
            category=extract_category(raw.url, markdown),
            content=markdown,
            summary=summary,
            ai_cleaned=ai_cleaned,
            matched_selector=raw.matched_selector,
        )

    def _write(self, articles: list[Article], date_folder: Path, today: str) -> None:
        saved = self.writer.write_all(articles, date_folder)
        self.result.saved = saved
        for article in articles:
            self.tracking.add(article, today)
        self.tracking.save()
        # Erst das Manifest, dann zippen – das ZIP enthält die manifest.json.
        update_manifest(date_folder)
        create_zip(date_folder)
        log.info('%d Artikel gespeichert in %s', saved, date_folder, extra={'icon': '✓'})

    # ------------------------------------------------------------------ Wächter

    def _check_blocked(self, page) -> None:
        result = self.blocking.read(page, self.ctx)
        if not result.verdict:
            return
        self._blocks += 1
        self.debug.capture(page.page, 'blocked', sensors=[result])
        if self._blocks > len(BLOCK_BACKOFF_S):
            raise BlockedError(result.describe())
        delay = BLOCK_BACKOFF_S[self._blocks - 1]
        log.warning('Blockade erkannt (%s) – warte %ds', result.reason, delay)
        time.sleep(delay)
        raise TransientScrapeError('Blockade – nach Backoff erneut versuchen')

    def _exit_code(self) -> int:
        attempted = self.result.new_links
        if attempted and self.result.failed / attempted > self.cfg.max_failure_ratio:
            log.error('Fehlerquote %.0f%% über dem Limit von %.0f%%',
                      100 * self.result.failed / attempted,
                      100 * self.cfg.max_failure_ratio)
            return EXIT_FAILED
        return EXIT_OK

    def _finish(self, started: float, exit_code: int) -> RunResult:
        self.result.duration_s = time.monotonic() - started
        self.result.exit_code = exit_code
        log.info('Lauf beendet: %s', self.result.summary_line(),
                 extra={'icon': '✓' if exit_code == EXIT_OK else '✗'})
        return self.result


class NZZScraper:
    """Fassade für scheduler.py – gleicher Vertrag wie bisher."""

    def __init__(self, config: ScraperConfig | None = None):
        self.cfg = config or ScraperConfig.from_env()

    def run(self) -> bool:
        return ScraperRun(self.cfg).execute().ok

    def delete_recent_articles(self, hours: int = 12) -> int:
        store = TrackingStore(self.cfg.tracking_file).load()
        removed, dates = store.delete_recent(hours, self.cfg.output_dir)
        store.save()
        for date_str in dates:
            folder = self.cfg.output_dir / date_str
            if folder.exists():
                update_manifest(folder)
                create_zip(folder)
        log.info('%d Artikel gelöscht und aus dem Tracking entfernt', removed,
                 extra={'icon': '✓'})
        return removed
