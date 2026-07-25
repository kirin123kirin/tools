from __future__ import annotations

import argparse
import itertools
import logging
import tempfile
import webbrowser
from pathlib import Path

from tools.common.clipboard import (
    get_clipboard_html_fragment,
    get_clipboard_text,
    has_clipboard_html,
    has_clipboard_text,
)
from tools.common.markdown_html import markdown_to_html_fragment
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_PREVIEW_FILENAME = "tools_clipview_preview.html"

_STYLE = """\
:root { color-scheme: light dark; }
body {
  max-width: 46rem;
  margin: 2rem auto;
  padding: 0 1rem;
  font-family: -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
  color: #222;
  background: #fff;
}
table { border-collapse: collapse; margin: 1rem 0; }
th, td { border: 1px solid #999; padding: 0.4rem 0.8rem; }
pre {
  background: #f5f5f5;
  padding: 0.8rem;
  overflow-x: auto;
  font-family: Consolas, "Courier New", monospace;
}
code { font-family: Consolas, "Courier New", monospace; }
blockquote {
  border-left: 4px solid #ccc;
  margin-left: 0;
  padding-left: 1rem;
  color: #555;
}
@media (prefers-color-scheme: dark) {
  body { color: #ddd; background: #1e1e1e; }
  th, td { border-color: #555; }
  pre { background: #2a2a2a; }
  blockquote { border-left-color: #555; color: #aaa; }
}
"""


def wrap_preview_html(body_fragment: str) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<title>clipview preview</title>
<style>
{_STYLE}
</style>
</head>
<body>
{body_fragment}
</body>
</html>
"""


class ClipviewProcessor(Processor):
    """Preview clipboard Markdown or HTML in the default browser.

    Unlike the other clip* commands, this one never modifies the clipboard;
    it only reads it and writes a temporary preview file.
    """

    name = "clipview"
    help = "クリップボードのMarkdown/HTMLをブラウザでプレビューする"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--markdown", action="store_true", help="入力をMarkdownとして解釈する"
        )
        group.add_argument("--html", action="store_true", help="入力をHTMLとして解釈する")
        parser.add_argument(
            "--no-open", action="store_true", help="ブラウザを開かず、パスの表示のみ行う"
        )

    def run(self, args: argparse.Namespace) -> int:
        body_fragment = self._resolve_body_fragment(args)

        if not body_fragment.strip():
            raise SystemExit("変換結果が空です")

        html = wrap_preview_html(body_fragment)

        preview_path = Path(tempfile.gettempdir()) / _PREVIEW_FILENAME
        try:
            preview_path.write_text(html, encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"一時ファイルの書き込みに失敗しました: {preview_path}") from exc

        logger.info("プレビューを書き出しました: %s", preview_path)
        print(preview_path)

        if not args.no_open:
            timestamp = _current_timestamp()
            url = f"{preview_path.as_uri()}?v={timestamp}"
            webbrowser.open(url)

        return 0

    def _resolve_body_fragment(self, args: argparse.Namespace) -> str:
        has_html = has_clipboard_html()
        has_text = has_clipboard_text()

        if args.markdown:
            if not has_text:
                raise SystemExit("クリップボードにテキストがありません")
            logger.info("--markdown指定: Markdownとして変換します")
            return markdown_to_html_fragment(get_clipboard_text())

        if args.html:
            if not has_html and not has_text:
                raise SystemExit("クリップボードにHTMLがありません")
            logger.info("--html指定: HTMLとして解釈します")
            return get_clipboard_html_fragment() if has_html else get_clipboard_text()

        if has_html:
            logger.info("CF_HTMLを検出したためHTMLとしてプレビューします")
            return get_clipboard_html_fragment()
        if has_text:
            logger.info("CF_UNICODETEXTのみのためMarkdownとして変換します")
            return markdown_to_html_fragment(get_clipboard_text())

        raise SystemExit("クリップボードにプレビューできる内容がありません")


_query_counter = itertools.count()


def _current_timestamp() -> str:
    """Cache-busting query value: wall-clock time plus a per-process counter,
    so consecutive calls within the same clock tick still differ.
    """
    import time

    return f"{time.time_ns()}-{next(_query_counter)}"
