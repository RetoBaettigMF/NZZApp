"""NZZ-Scraper: Page-Models, Sensoren und Mobilgerät-Emulation."""
from .config import ScraperConfig
from .logging_setup import get_logger, setup_logging
from .models import Article, PageType, RunResult

__version__ = '3.0.0'
__all__ = ['ScraperConfig', 'Article', 'PageType', 'RunResult',
           'NZZScraper', 'ScraperRun', 'setup_logging', 'get_logger', '__version__']


def __getattr__(name: str):
    # Träge, damit `import nzz_scraper` nicht Playwright hochzieht.
    if name in ('NZZScraper', 'ScraperRun'):
        from .pipeline import runner
        return getattr(runner, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
