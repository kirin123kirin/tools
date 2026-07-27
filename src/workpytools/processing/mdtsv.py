from __future__ import annotations

import argparse
import csv
import io
import logging
import re

from workpytools.common.clipboard import copy_text_to_clipboard, get_clipboard_text
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_PIPE_ESCAPE = "\x00PIPE\x00"  # セル分割前にエスケープ済みパイプを退避する一時トークン


def _is_markdown_table(text: str) -> bool:
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) < 2:
        return False
    if not all(line.strip().startswith("|") and line.strip().endswith("|") for line in lines):
        return False
    separator = lines[1].strip()
    return bool(re.fullmatch(r"\|[\s:|-]+\|", separator)) and "-" in separator


def _is_tsv(text: str) -> bool:
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return False
    return all("\t" in line for line in lines)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    escaped = stripped.replace("\\|", _PIPE_ESCAPE)
    cells = [cell.strip().replace(_PIPE_ESCAPE, "|") for cell in escaped.split("|")]
    return cells


def _is_separator_row(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"\|[\s:|-]+\|", stripped)) and "-" in stripped


def markdown_table_to_tsv(text: str) -> str:
    lines = [line for line in text.split("\n") if line.strip()]

    table_count = 0
    data_rows: list[list[str]] = []
    br_replaced = False

    for line in lines:
        if _is_separator_row(line):
            table_count += 1
            continue
        cells = _split_table_row(line)
        new_cells = []
        for cell in cells:
            if "<br>" in cell or "<br/>" in cell or "<br />" in cell:
                br_replaced = True
                cell = re.sub(r"<br\s*/?>", " ", cell)
            new_cells.append(cell)
        data_rows.append(new_cells)

    if table_count > 1:
        logger.info("表が%d個検出されたため、1つのTSVに連結します", table_count)
    if br_replaced:
        logger.warning("セル内の改行(<br>)はTSVで表現できないため、スペースに置き換えました")

    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    for row in data_rows:
        writer.writerow(row)
    return out.getvalue().rstrip("\n")


def tsv_to_markdown_table(text: str) -> str:
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    rows = [row for row in reader if row]

    br_replaced = False
    processed_rows = []
    for row in rows:
        new_row = []
        for cell in row:
            cell = cell.replace("\\", "\\\\").replace("|", "\\|")
            if "\n" in cell:
                br_replaced = True
                cell = cell.replace("\n", "<br>")
            new_row.append(cell)
        processed_rows.append(new_row)

    max_cols = max((len(row) for row in processed_rows), default=0)
    for row in processed_rows:
        while len(row) < max_cols:
            row.append("")

    if br_replaced:
        logger.warning("セル内の改行を <br> に置き換えました")

    lines = []
    if processed_rows:
        header = processed_rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for row in processed_rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


class MdtsvProcessor(Processor):
    """Convert clipboard contents between a Markdown table and TSV.

    Direction is auto-detected from the plain-text content (CF_UNICODETEXT
    only; CF_HTML is never consulted, since Excel's HTML is noisier than
    reconstructing from its TSV payload).
    """

    name = "mdtsv"
    help = "クリップボードのMarkdownの表とTSVを相互変換する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--to-tsv", action="store_true", help="入力をMarkdownの表とみなしTSVに変換する"
        )
        group.add_argument(
            "--to-table", action="store_true", help="入力をTSVとみなしMarkdownの表に変換する"
        )

    def run(self, args: argparse.Namespace) -> int:
        direction = self._resolve_direction(args)

        source_text = get_clipboard_text()

        if direction == "to_tsv":
            result = markdown_table_to_tsv(source_text)
            label = "Markdownの表 → TSV"
        else:
            result = tsv_to_markdown_table(source_text)
            label = "TSV → Markdownの表"

        if not result.strip():
            raise SystemExit("変換結果が空です")

        copy_text_to_clipboard(result)
        print(f"{label} に変換しました")
        return 0

    def _resolve_direction(self, args: argparse.Namespace) -> str:
        try:
            source_text = get_clipboard_text()
        except Exception as exc:
            raise SystemExit("変換できるテキストがありません") from exc

        if args.to_tsv:
            if not _is_markdown_table(source_text):
                raise SystemExit("入力をMarkdownの表として解釈できません")
            return "to_tsv"

        if args.to_table:
            logger.info("--to-table指定: タブの有無にかかわらずTSVとして扱います")
            return "to_table"

        if _is_markdown_table(source_text):
            logger.info("Markdownの表を検出したため 表 → TSV に変換します")
            return "to_tsv"
        if _is_tsv(source_text):
            logger.info("TSVを検出したため TSV → 表 に変換します")
            return "to_table"

        raise SystemExit(
            "入力をMarkdownの表ともTSVとも解釈できません"
            "（Markdownの表全体、またはタブ区切りのテキストをコピーしてください）"
        )
