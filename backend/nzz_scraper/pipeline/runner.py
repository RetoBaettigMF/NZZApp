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
                       PaywallSensor)
from .auth_manager import AuthManager
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
        self.quality = ContentQualitySensor()
        self.blocking = BlockingSensor()
        self.result = RunResult()
        self._ai = None
        self._ai_failed = False
        self._blocks = 0

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

            links = self._collect_links(page)
            self.result.links_found = len(links)

            new_links = [u for u in links if not self.tracking.is_scraped(u)]
            total_new = len(new_links)
            if limit:
                new_links = new_links[:limit]
            self.result.new_links = len(new_links)
            log.info('%d Links gefunden, %d neu%s', len(links), total_new,
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

    def _collect_links(self, page) -> list[str]:
        feed = LatestArticlesPage(page, self.ctx)
        feed.open(self.cfg.base_url).assert_ready()
        feed.dismiss_overlays()
        self._check_blocked(feed)
        return feed.collect_links(max_links=self.cfg.max_links)

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

        raw = article_page.extract()
        markdown = html_fragment_to_markdown(raw.html)

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
