"""Debug-Artefakte: Screenshot, HTML und Sensor-Metadaten bei Fehlern."""
from __future__ import annotations

import json
import shutil
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .logging_setup import get_logger

log = get_logger(__name__)


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


class DebugArtifacts:
    """Schreibt pro Vorfall ein Zeitstempel-Verzeichnis unter `root`."""

    def __init__(self, root: Path, enabled: bool = True, keep_last: int = 50):
        self.root = Path(root)
        self.enabled = enabled
        self.keep_last = keep_last

    def capture(self, page, label: str, *, error: BaseException | None = None,
                sensors: Sequence[Any] = (), extra: dict | None = None) -> Path | None:
        """Legt screenshot.png, page.html und meta.json ab. Wirft nie."""
        if not self.enabled:
            return None
        try:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
            target = self.root / f'{stamp}-{label}'
            target.mkdir(parents=True, exist_ok=True)

            meta: dict[str, Any] = {
                'label': label,
                'timestamp': datetime.now().isoformat(),
                'sensors': [_jsonable(s) for s in sensors],
            }
            if extra:
                meta['extra'] = _jsonable(extra)
            if error is not None:
                meta['error'] = {
                    'type': type(error).__name__,
                    'message': str(error),
                    'traceback': ''.join(
                        traceback.format_exception(type(error), error, error.__traceback__)),
                }

            if page is not None:
                try:
                    meta['url'] = page.url
                    meta['title'] = page.title()
                except Exception:
                    pass
                try:
                    page.screenshot(path=str(target / 'screenshot.png'), full_page=True)
                except Exception as e:
                    meta['screenshot_error'] = str(e)
                try:
                    (target / 'page.html').write_text(page.content(), encoding='utf-8')
                except Exception as e:
                    meta['html_error'] = str(e)

            (target / 'meta.json').write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
            log.info('Debug-Artefakte: %s', target)
            self.prune()
            return target
        except Exception as e:                                  # nie den Lauf killen
            log.warning('Debug-Dump fehlgeschlagen: %s', e)
            return None

    def prune(self) -> None:
        """Behält nur die jüngsten `keep_last` Verzeichnisse."""
        try:
            dirs = sorted((d for d in self.root.iterdir() if d.is_dir() and d.name[0].isdigit()),
                          key=lambda d: d.name)
            for old in dirs[:-self.keep_last]:
                shutil.rmtree(old, ignore_errors=True)
        except (OSError, FileNotFoundError):
            pass
