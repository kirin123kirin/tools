from __future__ import annotations

import argparse
import logging

from tools.common.browser_preview import write_and_open
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
_SVG_PREVIEW_FILENAME = "tools_clipview_preview.svg"

# markdown-it-pyが```mermaidフェンスをレンダリングすると
# <pre><code class="language-mermaid">...</code></pre> になる。
# この文字列の有無だけを見て、Mermaidブロックの存在を検出する
# （存在しない通常のMarkdown/HTMLプレビューでは外部通信を一切発生させないため）。
_MERMAID_CLASS_MARKER = 'class="language-mermaid"'

_MERMAID_CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

_MERMAID_SCRIPT = f"""\
<script src="{_MERMAID_CDN_URL}"></script>
<script>
  document.querySelectorAll("pre code.language-mermaid").forEach((el) => {{
    const pre = el.parentElement;
    const div = document.createElement("div");
    div.className = "mermaid";
    div.textContent = el.textContent;
    pre.replaceWith(div);
  }});
  mermaid.initialize({{ startOnLoad: true }});
</script>
"""

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
    mermaid_script = _MERMAID_SCRIPT if _MERMAID_CLASS_MARKER in body_fragment else ""
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
{mermaid_script}</body>
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
        group.add_argument("--svg", action="store_true", help="入力をSVGとして解釈する")
        parser.add_argument(
            "--no-open", action="store_true", help="ブラウザを開かず、パスの表示のみ行う"
        )

    def run(self, args: argparse.Namespace) -> int:
        svg_text = self._resolve_svg(args)
        if svg_text is not None:
            if not svg_text.strip():
                raise SystemExit("変換結果が空です")
            try:
                preview_path = write_and_open(svg_text, _SVG_PREVIEW_FILENAME, args.no_open)
            except RuntimeError as exc:
                raise SystemExit(str(exc)) from exc
            print(preview_path)
            return 0

        body_fragment = self._resolve_body_fragment(args)

        if not body_fragment.strip():
            raise SystemExit("変換結果が空です")

        if _MERMAID_CLASS_MARKER in body_fragment:
            logger.info(
                "Mermaidブロックを検出したため、CDN(%s)からmermaid.jsを読み込みます",
                _MERMAID_CDN_URL,
            )

        html = wrap_preview_html(body_fragment)

        try:
            preview_path = write_and_open(html, _PREVIEW_FILENAME, args.no_open)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc

        print(preview_path)
        return 0

    def _resolve_svg(self, args: argparse.Namespace) -> str | None:
        has_text = has_clipboard_text()

        if args.svg:
            if not has_text:
                raise SystemExit("クリップボードにテキストがありません")
            logger.info("--svg指定: SVGとして扱います")
            return get_clipboard_text()

        if args.markdown or args.html:
            return None

        if has_text:
            text = get_clipboard_text()
            if text.lstrip().startswith("<svg"):
                logger.info("SVGコードを検出したため、そのままファイルにしてプレビューします")
                return text

        return None

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
