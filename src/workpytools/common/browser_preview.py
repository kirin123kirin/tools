from __future__ import annotations

import itertools
import logging
import tempfile
import time
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

_query_counter = itertools.count()


def cache_busting_query() -> str:
    """Wall-clock time plus a per-process counter, so consecutive calls
    within the same clock tick still differ. Used to defeat the browser's
    tendency to not reload a fixed-name file:// URL it already has open.
    """
    return f"{time.time_ns()}-{next(_query_counter)}"


def write_and_open(html: str, filename: str, no_open: bool) -> Path:
    """Write `html` to a fixed-name file under %TEMP% and open it in the
    default browser (unless `no_open`). Reused by every command that
    previews a result in the browser (clipview, profiler --view, ...).
    """
    preview_path = Path(tempfile.gettempdir()) / filename
    try:
        preview_path.write_text(html, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"一時ファイルの書き込みに失敗しました: {preview_path}") from exc

    logger.info("プレビューを書き出しました: %s", preview_path)

    if not no_open:
        url = f"{preview_path.as_uri()}?v={cache_busting_query()}"
        webbrowser.open(url)

    return preview_path
