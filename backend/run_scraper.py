#!/usr/bin/env python3
"""NZZ Artikel Scraper – Einstiegspunkt.

    python run_scraper.py                 # inkrementeller Lauf
    python run_scraper.py --rescrape      # letzte 12h löschen und neu scrapen
    python run_scraper.py --limit 3 --dry-run
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nzz_scraper.cli import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
