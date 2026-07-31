from __future__ import annotations

import argparse
import base64
import io
import logging

from workpytools.common.browser_preview import write_and_open
from workpytools.common.clipboard import (
    ClipboardImageError,
    get_clipboard_html_fragment,
    get_clipboard_text,
    has_clipboard_html,
    has_clipboard_text,
    load_image,
)
from workpytools.common.markdown_html import markdown_to_html_fragment
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_PREVIEW_FILENAME = "workpytools_clipview_preview.html"
_SVG_PREVIEW_FILENAME = "workpytools_clipview_preview.svg"

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
.checkerboard {
  display: inline-block;
  max-width: 100%;
  background-image:
    linear-gradient(45deg, #ccc 25%, transparent 25%),
    linear-gradient(-45deg, #ccc 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #ccc 75%),
    linear-gradient(-45deg, transparent 75%, #ccc 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
.checkerboard img { display: block; max-width: 100%; height: auto; }
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

        image_fragment = self._resolve_image_fragment()
        if image_fragment is not None:
            return image_fragment

        raise SystemExit("クリップボードにプレビューできる内容がありません")

    def _resolve_image_fragment(self) -> str | None:
        """HTML/text fragment for clipboard image data (e.g. `touka`'s output
        copied via `copy_image_to_clipboard`), or None if the clipboard holds
        no usable image. The image is embedded as a base64 data URI over a
        checkerboard background, so transparency is visible at a glance
        without writing any file besides the preview HTML itself."""
        try:
            loaded = load_image(None)
        except ClipboardImageError:
            return None

        logger.info("クリップボードの画像データを検出したためプレビューします")
        with io.BytesIO() as buf:
            loaded.image.save(buf, "PNG")
            data_uri = base64.b64encode(buf.getvalue()).decode("ascii")

        return (
            f'<div class="checkerboard">'
            f'<img src="data:image/png;base64,{data_uri}" alt="clipboard image">'
            f"</div>"
        )
