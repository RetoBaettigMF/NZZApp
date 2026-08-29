#!/usr/bin/env python3
"""Scheduler - Startet den Scraper täglich um 06:00 Uhr."""
import os
import sys
import time
from datetime import datetime

import schedule

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nzz_scraper import NZZScraper, ScraperConfig, get_logger, setup_logging

log = get_logger(__name__)


def job():
    """Der tägliche Scraping-Job."""
    log.info('Starte täglichen Scraper')
    scraper = NZZScraper()
    success = scraper.run()
    if success:
        log.info('Job erfolgreich abgeschlossen', extra={'icon': '✓'})
    else:
        log.error('Job fehlgeschlagen')
    log.info('Nächster Lauf: %s', schedule.next_run())


def run_scheduler():
    """Startet den Scheduler."""
    cfg = ScraperConfig.from_env()
    setup_logging(os.getenv('LOG_LEVEL', 'INFO'), cfg.log_file)

    log.info('NZZ Scraper Scheduler – Job läuft täglich um 06:00 Uhr')
    schedule.every().day.at('06:00').do(job)

    if len(sys.argv) > 1 and sys.argv[1] == '--run-now':
        log.info('Führe sofortigen Lauf aus')
        job()

    log.info('Nächster Lauf: %s', schedule.next_run())
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log.info('Scheduler beendet', extra={'icon': '✓'})


if __name__ == '__main__':
    run_scheduler()
