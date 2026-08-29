"""Zentrale Konfiguration – ein einziger load_dotenv()-Aufruf im ganzen Paket."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigError

BACKEND_DIR = Path(__file__).resolve().parent.parent

_dotenv_loaded = False


def _load_env_once() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv(BACKEND_DIR / '.env')
        _dotenv_loaded = True


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'ja', 'on')


@dataclass(frozen=True)
class ScraperConfig:
    """Alle Laufzeit-Parameter. Pfade sind immer absolut."""

    email: str | None
    password: str | None
    output_dir: Path
    base_url: str
    session_file: Path
    debug_dir: Path
    log_file: Path | None
    site_root: str = 'https://www.nzz.ch'
    device: str = 'Pixel 7'
    chromium_channel: str | None = None
    headless: bool = True
    allow_anonymous: bool = False
    force_anonymous: bool = False   # gar nicht erst einloggen (Tests)
    use_ai: bool = True
    trace: bool = False

    nav_timeout_ms: int = 30_000
    default_timeout_ms: int = 15_000
    selector_timeout_ms: int = 3_000
    article_budget_s: float = 90.0
    run_budget_s: float = 3600.0

    max_links: int = 200
    max_failure_ratio: float = 0.30
    max_relogins: int = 3

    @property
    def tracking_file(self) -> Path:
        return self.output_dir / 'scraped_articles.json'

    @classmethod
    def from_env(cls, **overrides) -> "ScraperConfig":
        """Baut die Config aus .env; `overrides` haben Vorrang.

        Der Smoke-Test nutzt die Overrides, um garantiert in ein tmp-Verzeichnis
        zu schreiben.
        """
        _load_env_once()

        def _path(value, default: Path) -> Path:
            if value is None:
                return default
            return Path(value).expanduser().resolve()

        base = cls(
            email=os.getenv('NZZ_EMAIL') or None,
            password=os.getenv('NZZ_PASSWORD') or None,
            output_dir=_path(os.getenv('OUTPUT_DIR'), BACKEND_DIR / 'articles'),
            base_url=os.getenv('BASE_URL', 'https://www.nzz.ch/neueste-artikel'),
            session_file=_path(os.getenv('NZZ_SESSION_FILE'),
                               BACKEND_DIR / '.state' / 'nzz_storage_state.json'),
            debug_dir=_path(os.getenv('NZZ_DEBUG_DIR'), BACKEND_DIR / 'debug'),
            log_file=_path(os.getenv('NZZ_LOG_FILE'), BACKEND_DIR / 'scraper_log.txt'),
            device=os.getenv('NZZ_DEVICE', 'Pixel 7'),
            chromium_channel=os.getenv('NZZ_CHROMIUM_CHANNEL') or None,
            headless=_bool_env('NZZ_HEADLESS', True),
        )

        # Pfad-Overrides ebenfalls normalisieren
        for key in ('output_dir', 'session_file', 'debug_dir', 'log_file'):
            if key in overrides and overrides[key] is not None:
                overrides[key] = Path(overrides[key]).expanduser().resolve()

        return replace(base, **overrides) if overrides else base

    def validate(self) -> None:
        """Prüft die Config; wirft ConfigError."""
        if not self.output_dir.parent.exists():
            raise ConfigError(
                f"Elternverzeichnis von OUTPUT_DIR existiert nicht: {self.output_dir.parent}")
        if not (self.allow_anonymous or self.force_anonymous) and not (self.email and self.password):
            raise ConfigError(
                "NZZ_EMAIL/NZZ_PASSWORD fehlen in der .env. Ohne Login liefert NZZ "
                "nur Paywall-Anrisse – Abbruch. Mit --allow-anonymous trotzdem starten.")
        if self.max_failure_ratio <= 0 or self.max_failure_ratio > 1:
            raise ConfigError(f"max_failure_ratio muss in (0, 1] liegen, ist {self.max_failure_ratio}")

    def ensure_dirs(self) -> None:
        """Legt Ausgabe-, State- und Debug-Verzeichnis an."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.session_file.parent.chmod(0o700)
        except OSError:
            pass
