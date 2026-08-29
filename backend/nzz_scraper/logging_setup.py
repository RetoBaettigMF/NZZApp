"""Logging-Setup: Konsole mit Icons, Datei ohne – rotierend."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

ROOT_LOGGER = 'nzz_scraper'

_ICONS = {
    logging.DEBUG: '·',
    logging.INFO: 'ℹ',
    logging.WARNING: '⚠',
    logging.ERROR: '✗',
    logging.CRITICAL: '🔥',
}
_ASCII = {
    logging.DEBUG: '.',
    logging.INFO: 'i',
    logging.WARNING: '!',
    logging.ERROR: 'x',
    logging.CRITICAL: 'X',
}
_ASCII_FALLBACK = {'·': '.', 'ℹ': 'i', '⚠': '!', '✗': 'x', '🔥': 'X', '✓': '+', '⊘': '-'}


class IconFormatter(logging.Formatter):
    """Setzt `record.icon` aus dem Level – oder aus `extra={'icon': '✓'}`."""

    def __init__(self, fmt: str, datefmt: str | None = None, *, emoji: bool = True):
        super().__init__(fmt, datefmt)
        self.emoji = emoji

    def format(self, record: logging.LogRecord) -> str:
        icon = getattr(record, 'icon', None)
        if icon is None:
            icon = (_ICONS if self.emoji else _ASCII).get(record.levelno, ' ')
        elif not self.emoji:
            icon = _ASCII_FALLBACK.get(icon, icon)
        record.icon = icon
        return super().format(record)


def _emoji_supported(stream) -> bool:
    if os.getenv('NO_COLOR') or os.getenv('NZZ_NO_EMOJI'):
        return False
    enc = getattr(stream, 'encoding', None) or ''
    return 'utf' in enc.lower()


def setup_logging(level: str = 'INFO', log_file: Path | None = None, *,
                  file_level: str = 'DEBUG', emoji: bool | None = None,
                  stream=None) -> logging.Logger:
    """Konfiguriert den Wurzel-Logger `nzz_scraper` idempotent."""
    stream = stream or sys.stderr
    if emoji is None:
        emoji = _emoji_supported(stream)

    log = logging.getLogger(ROOT_LOGGER)
    log.setLevel(logging.DEBUG)          # Handler filtern, nicht der Logger
    log.propagate = False
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()

    console = logging.StreamHandler(stream)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(IconFormatter(
        '%(asctime)s %(icon)s %(name)-28s %(message)s', '%H:%M:%S', emoji=emoji))
    log.addHandler(console)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=5, encoding='utf-8')
        fh.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
        # Ohne Icon: grep/awk auf der Datei soll einfach bleiben.
        fh.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)-8s %(name)s %(message)s'))
        log.addHandler(fh)

    for noisy in ('urllib3', 'requests', 'asyncio'):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log


def get_logger(name: str) -> logging.Logger:
    """`get_logger(__name__)` – liefert immer einen Kind-Logger von nzz_scraper."""
    if name.startswith(ROOT_LOGGER):
        return logging.getLogger(name)
    return logging.getLogger(f'{ROOT_LOGGER}.{name}')
