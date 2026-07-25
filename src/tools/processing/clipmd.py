from __future__ import annotations

import argparse
import logging

from tools.common.clipboard import (
    copy_html_and_text_to_clipboard,
    copy_text_to_clipboard,
    get_clipboard_html_fragment,
    get_clipboard_text,
    has_clipboard_html,
    has_clipboard_text,
)
from tools.common.markdown_html import markdown_to_html_fragment
from tools.processing.base import Processor

logger = logging.getLogger(__name__)


def _preprocess_table_html(soup: object) -> list[str]:
    """Rewrite <table> elements for markdownify: promote first row to <thead> when
    missing, pad colspan/rowspan cells with empty cells so column counts line up.
    Returns warning messages describing what was rewritten or will be lost.
    """
    from bs4 import Tag

    warnings: list[str] = []

    for table in soup.find_all("table"):  # type: ignore[attr-defined]
        if not table.find("thead"):
            rows = table.find_all("tr")
            if rows:
                first_row = rows[0]
                for cell in first_row.find_all("td"):
                    cell.name = "th"
                thead = soup.new_tag("thead")  # type: ignore[attr-defined]
                first_row.wrap(thead)

        for row in table.find_all("tr"):
            for cell in row.find_all(["td", "th"]):
                colspan = cell.get("colspan")
                if colspan and int(colspan) > 1:
                    n = int(colspan) - 1
                    warnings.append(
                        f"表のセル結合(colspan={colspan})を検出したため、空セルで列数を揃えました"
                    )
                    del cell["colspan"]
                    for _ in range(n):
                        empty: Tag = soup.new_tag(cell.name)  # type: ignore[attr-defined]
                        cell.insert_after(empty)
                if cell.get("rowspan"):
                    warnings.append(
                        f"表のセル結合(rowspan={cell.get('rowspan')})を検出しました"
                        "（行方向の結合は補完されません）"
                    )
                    del cell["rowspan"]

            for cell in row.find_all(["td", "th"]):
                if cell.find(["p", "ul", "ol", "br"]):
                    warnings.append("表のセル内に改行やリストがあり、情報が失われました")
                if cell.find("img"):
                    warnings.append("表のセル内の画像は変換で失われました")

    return warnings


def _collect_alignment(soup: object) -> dict[int, dict[int, str]]:
    """Collect per-table, per-column text-align, keyed by table index then column index."""
    alignments: dict[int, dict[int, str]] = {}
    for table_idx, table in enumerate(soup.find_all("table")):  # type: ignore[attr-defined]
        header_row = table.find("tr")
        if header_row is None:
            continue
        col_aligns: dict[int, str] = {}
        for col_idx, cell in enumerate(header_row.find_all(["th", "td"])):
            style = cell.get("style", "")
            if "text-align:right" in style or "text-align: right" in style:
                col_aligns[col_idx] = "right"
            elif "text-align:center" in style or "text-align: center" in style:
                col_aligns[col_idx] = "center"
            elif "text-align:left" in style or "text-align: left" in style:
                col_aligns[col_idx] = "left"
        if col_aligns:
            alignments[table_idx] = col_aligns
    return alignments


def _apply_alignment_to_markdown(markdown_text: str, alignments: dict[int, dict[int, str]]) -> str:
    """Rewrite Markdown table separator rows (`| --- |`) to reflect collected alignment."""
    if not alignments:
        return markdown_text

    lines = markdown_text.split("\n")
    table_idx = -1
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        is_separator = (
            line.strip().startswith("|")
            and set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set()
            and "-" in line
        )
        if is_separator and i > 0 and lines[i - 1].strip().startswith("|"):
            table_idx += 1
            col_aligns = alignments.get(table_idx, {})
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            new_cols = []
            for col_idx, _ in enumerate(cols):
                align = col_aligns.get(col_idx)
                if align == "right":
                    new_cols.append("---:")
                elif align == "center":
                    new_cols.append(":---:")
                elif align == "left":
                    new_cols.append(":---")
                else:
                    new_cols.append("---")
            result.append("| " + " | ".join(new_cols) + " |")
        else:
            result.append(line)
        i += 1
    return "\n".join(result)


def _collect_image_warnings(soup: object) -> list[str]:
    warnings: list[str] = []
    for img in soup.find_all("img"):  # type: ignore[attr-defined]
        src = img.get("src", "")
        if src.startswith("file:///"):
            if "msohtmlclip" in src.lower():
                warnings.append(
                    "画像がWord由来の一時ファイルを参照しています"
                    f"（後でリンクが切れる可能性があります）: {src}"
                )
            else:
                warnings.append(
                    "画像がローカルの一時ファイルらしきパスを参照しています"
                    f"（後でリンクが切れる可能性があります）: {src}"
                )
        elif src.startswith("data:"):
            b64_part = src.split(",", 1)[1] if "," in src else ""
            size_kb = len(b64_part) * 3 / 4 / 1024
            warnings.append(f"データURI画像を検出しました（約{size_kb:.1f}KBの1行になります）")
    return warnings


def html_to_markdown(html_fragment: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import MarkdownConverter

    soup = BeautifulSoup(html_fragment, "html.parser")

    for warning in _preprocess_table_html(soup):
        logger.warning(warning)
    for warning in _collect_image_warnings(soup):
        logger.warning(warning)

    alignments = _collect_alignment(soup)

    markdown_text = MarkdownConverter().convert_soup(soup).strip()
    markdown_text = _apply_alignment_to_markdown(markdown_text, alignments)
    return markdown_text


class ClipmdProcessor(Processor):
    """Convert clipboard contents between Markdown and rich text (HTML).

    Direction is auto-detected from what's on the clipboard: CF_HTML present
    means rich text was copied (convert HTML -> Markdown); CF_UNICODETEXT
    only means plain text was copied (convert Markdown -> rich text).
    """

    name = "clipmd"
    help = "クリップボードのMarkdownとリッチテキストを相互変換する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--to-markdown", action="store_true", help="入力をHTMLとみなしMarkdownに変換する"
        )
        group.add_argument(
            "--to-rich", action="store_true", help="入力をMarkdownとみなしリッチテキストに変換する"
        )

    def run(self, args: argparse.Namespace) -> int:
        direction, use_html_source = self._resolve_direction(args)

        if direction == "to_markdown":
            fragment = get_clipboard_html_fragment() if use_html_source else get_clipboard_text()
            markdown_text = html_to_markdown(fragment)
            if not markdown_text.strip():
                raise SystemExit("変換結果が空です")
            copy_text_to_clipboard(markdown_text)
            print("HTML → Markdown に変換しました")
        else:
            source_text = get_clipboard_text()
            html_fragment = markdown_to_html_fragment(source_text)
            if not html_fragment.strip():
                raise SystemExit("変換結果が空です")
            copy_html_and_text_to_clipboard(html_fragment, source_text)
            print("Markdown → リッチテキスト に変換しました")

        return 0

    def _resolve_direction(self, args: argparse.Namespace) -> tuple[str, bool]:
        """Returns (direction, use_html_source_for_markdown_conversion)."""
        has_html = has_clipboard_html()
        has_text = has_clipboard_text()

        if args.to_markdown:
            if not has_html and not has_text:
                raise SystemExit("変換できるテキストがありません")
            if not has_html:
                logger.info(
                    "--to-markdown指定: CF_HTMLが無いためCF_UNICODETEXTをHTMLソースとして解釈します"
                )
                return "to_markdown", False
            return "to_markdown", True

        if args.to_rich:
            if not has_text:
                raise SystemExit("変換できるテキストがありません")
            if has_html:
                logger.info(
                    "--to-rich指定: CF_HTMLを無視しCF_UNICODETEXTをMarkdownとして解釈します"
                )
            return "to_rich", False

        if has_html:
            logger.info("CF_HTMLを検出したため HTML → Markdown に変換します")
            return "to_markdown", True
        if has_text:
            logger.info("CF_UNICODETEXTのみのため Markdown → リッチテキスト に変換します")
            return "to_rich", False

        raise SystemExit("変換できるテキストがありません")
