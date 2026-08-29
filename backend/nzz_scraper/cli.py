"""Kommandozeile des Scrapers."""
from __future__ import annotations

import argparse
from typing import Sequence

from .config import ScraperConfig
from .errors import EXIT_FAILED, ConfigError, ScraperError
from .logging_setup import get_logger, setup_logging

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='run_scraper.py', description='NZZ Artikel Scraper')
    # Unverändert gegenüber dem alten Scraper:
    p.add_argument('--rescrape', nargs='?', const=12, type=int, metavar='STUNDEN',
                   help='Löscht Artikel der letzten N Stunden und scrapt neu (Standard: 12)')
    p.add_argument('--limit', type=int, metavar='N',
                   help='Höchstens N neue Artikel scrapen')
    p.add_argument('--dry-run', action='store_true',
                   help='Alles durchlaufen, aber nichts schreiben')
    p.add_argument('--headed', action='store_true', help='Sichtbarer Browser')
    p.add_argument('--device', metavar='NAME', help='Playwright-Geräteprofil (Standard: Pixel 7)')
    p.add_argument('--output-dir', metavar='PFAD', help='Überschreibt OUTPUT_DIR')
    p.add_argument('--fresh-login', action='store_true',
                   help='Gespeicherte Session verwerfen und neu einloggen')
    p.add_argument('--allow-anonymous', action='store_true',
                   help='Ohne Login weiterlaufen, falls der Login scheitert')
    p.add_argument('--no-login', action='store_true',
                   help='Gar nicht einloggen – nur zum Prüfen der Paywall-Erkennung')
    p.add_argument('--no-ai', action='store_true', help='OpenRouter überspringen')
    p.add_argument('--pro-access', choices=['auto', 'yes', 'no'],
                   help='NZZ-Pro-Abo vorhanden? Standard: auto (einmal empirisch prüfen)')
    p.add_argument('--recheck-pro', action='store_true',
                   help='Gespeicherte Abo-Stufe verwerfen und neu ermitteln')
    p.add_argument('--trace', action='store_true', help='Playwright-Trace aufzeichnen')
    p.add_argument('--log-level', default='INFO',
                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    p.add_argument('--no-emoji', action='store_true', help='ASCII-Statuszeichen')
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    overrides = {}
    if args.headed:
        overrides['headless'] = False
    if args.device:
        overrides['device'] = args.device
    if args.output_dir:
        overrides['output_dir'] = args.output_dir
    if args.allow_anonymous:
        overrides['allow_anonymous'] = True
    if args.no_login:
        overrides['force_anonymous'] = True
    if args.no_ai:
        overrides['use_ai'] = False
    if args.trace:
        overrides['trace'] = True
    if args.pro_access:
        overrides['pro_access'] = args.pro_access

    try:
        cfg = ScraperConfig.from_env(**overrides)
        setup_logging(args.log_level, cfg.log_file,
                      emoji=False if args.no_emoji else None)
        cfg.validate()
        cfg.ensure_dirs()
    except ConfigError as e:
        setup_logging(args.log_level, None)
        log.critical('Konfiguration: %s', e)
        return 2

    from .pipeline.runner import NZZScraper, ScraperRun

    if args.fresh_login and cfg.session_file.exists():
        cfg.session_file.unlink()
        log.info('Gespeicherte Session verworfen')
    if args.recheck_pro and cfg.entitlement_file.exists():
        cfg.entitlement_file.unlink()
        log.info('Gespeicherte Abo-Stufe verworfen')

    try:
        if args.rescrape is not None:
            NZZScraper(cfg).delete_recent_articles(hours=args.rescrape)

        result = ScraperRun(cfg).execute(limit=args.limit, dry_run=args.dry_run)
        return result.exit_code
    except ScraperError as e:
        log.critical('%s: %s', type(e).__name__, e)
        return EXIT_FAILED
    except KeyboardInterrupt:
        log.warning('Abbruch durch Benutzer')
        return EXIT_FAILED
