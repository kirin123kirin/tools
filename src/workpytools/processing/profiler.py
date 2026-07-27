from __future__ import annotations

import argparse
import logging
from pathlib import Path

from workpytools.common.clipboard import copy_text_to_clipboard, get_clipboard_text
from workpytools.common.tabular import (
    DEFAULT_EMPTY_VALUES,
    ColumnProfile,
    Table,
    format_top,
    load_tables,
    profile_columns,
    read_csv_like,
)
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_HEADER = (
    "source",
    "sheet",
    "column",
    "rows",
    "filled",
    "empty",
    "fill_rate",
    "unique",
    "unique_rate",
    "is_filled",
    "is_unique",
    "key_score",
    "top",
)


def _profile_row(source: str, sheet: str, profile: ColumnProfile) -> list[str]:
    return [
        source,
        sheet,
        profile.column,
        str(profile.rows),
        str(profile.filled),
        str(profile.empty),
        f"{profile.fill_rate:.4f}",
        str(profile.unique),
        f"{profile.unique_rate:.4f}",
        str(profile.is_filled),
        str(profile.is_unique),
        f"{profile.key_score:.4f}",
        format_top(profile.top),
    ]


class ProfilerProcessor(Processor):
    """Profile every column of tabular data (CSV/TSV/Excel/JSON): fill rate,
    uniqueness, top values, and a key-likelihood score. Reads from a file or,
    with no argument, from the clipboard (e.g. a range copied from Excel).
    """

    name = "profiler"
    help = "表形式データの各列をプロファイルする（欠損・一意性・頻度上位・主キー候補）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="*",
            default=[],
            help="対象ファイル（複数・グロブ可）。省略時はクリップボードのTSVを読む",
        )
        parser.add_argument("-o", "--output", default=None, help="出力先パス（.tsv / .xlsx）")
        parser.add_argument(
            "--clip", action="store_true", help="結果をクリップボードにコピーする"
        )
        parser.add_argument(
            "--view", action="store_true", help="結果をブラウザでHTML表示する"
        )
        parser.add_argument("--sep", default=None, help="区切り文字（拡張子判定を上書き）")
        parser.add_argument(
            "--header",
            type=int,
            default=0,
            help="ヘッダー行のインデックス（0始まり、既定0）",
        )
        parser.add_argument(
            "--no-header", action="store_true", help="ヘッダーなしとして扱う"
        )
        parser.add_argument(
            "--top", type=int, default=10, help="頻度上位の表示件数（既定10、0で非表示）"
        )
        parser.add_argument(
            "--empty-values",
            default=None,
            help="空とみなす値のカンマ区切りリスト（既定値を置き換える）",
        )
        parser.add_argument(
            "--no-default-empty-values",
            action="store_true",
            help="既定の空値リストを無効化し、Noneと空文字だけを空とみなす",
        )

    def run(self, args: argparse.Namespace) -> int:
        empty_values = self._resolve_empty_values(args)

        sources = self._resolve_sources(args)
        has_excel = any(
            Path(s).suffix.lower() == ".xlsx" for s, _ in sources if s != "(clipboard)"
        )

        rows: list[list[str]] = [list(_HEADER)] if has_excel else [
            [h for h in _HEADER if h != "sheet"]
        ]

        for source_label, table_by_sheet in sources:
            for sheet_name, table in table_by_sheet.items():
                if not table.rows:
                    label = f"{source_label} [{sheet_name}]" if sheet_name else source_label
                    logger.warning("データ行が0件のためスキップします: %s", label)
                    continue
                for profile in profile_columns(table, top_n=args.top, empty_values=empty_values):
                    row = _profile_row(source_label, sheet_name, profile)
                    if not has_excel:
                        row = [v for v, h in zip(row, _HEADER, strict=True) if h != "sheet"]
                    rows.append(row)

        if len(rows) <= 1:
            raise SystemExit("プロファイル対象の列がありません（入力が空の可能性があります）")

        self._emit(rows, args)
        return 0

    def _resolve_empty_values(self, args: argparse.Namespace) -> frozenset[object]:
        if args.no_default_empty_values:
            base: frozenset[object] = frozenset({None, ""})
        else:
            base = DEFAULT_EMPTY_VALUES

        if args.empty_values:
            return frozenset(v.strip() for v in args.empty_values.split(","))
        return base

    def _resolve_sources(
        self, args: argparse.Namespace
    ) -> list[tuple[str, dict[str, Table]]]:
        if not args.path:
            try:
                text = get_clipboard_text()
            except Exception as exc:
                raise SystemExit("クリップボードにテキストがありません") from exc
            sep = args.sep if args.sep is not None else "\t"
            header_row = None if args.no_header else args.header
            table = read_csv_like(text, sep, header_row)
            return [("(clipboard)", {"": table})]

        from glob import glob

        results = []
        header_row = None if args.no_header else args.header
        for pattern in args.path:
            matches = glob(pattern) or [pattern]
            for filename in matches:
                path = Path(filename)
                try:
                    tables = load_tables(path, args.sep, header_row)
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
                except OSError as exc:
                    raise SystemExit(f"ファイルを読み込めません: {path}") from exc
                results.append((str(path), tables))

        if not results:
            raise SystemExit("対象ファイルが見つかりません")
        return results

    def _emit(self, rows: list[list[str]], args: argparse.Namespace) -> None:
        tsv_text = "\n".join("\t".join(row) for row in rows)

        if args.clip:
            copy_text_to_clipboard(tsv_text)
            print("プロファイル結果をコピーしました")
            return

        if args.view:
            self._view_in_browser(rows)
            return

        if args.output:
            self._write_output(rows, tsv_text, args.output)
            return

        print(tsv_text)

    def _write_output(self, rows: list[list[str]], tsv_text: str, output: str) -> None:
        output_path = Path(output)
        if output_path.suffix.lower() == ".xlsx":
            self._write_excel(rows, output_path)
        else:
            output_path.write_text(tsv_text, encoding="utf-8")
        logger.info("プロファイル結果を書き出しました: %s", output_path)
        print(output_path)

    def _write_excel(self, rows: list[list[str]], output_path: Path) -> None:
        import xlsxwriter

        header = rows[0]
        bad_cols = {i for i, h in enumerate(header) if h in ("is_filled", "is_unique")}

        with xlsxwriter.Workbook(str(output_path)) as workbook:
            worksheet = workbook.add_worksheet("profile")
            header_format = workbook.add_format(
                {"bold": True, "align": "center", "border": 1}
            )
            worksheet.write_row(0, 0, header, header_format)

            red_format = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
            for r, row in enumerate(rows[1:], start=1):
                worksheet.write_row(r, 0, row)
                for c in bad_cols:
                    if row[c] == "False":
                        worksheet.write(r, c, row[c], red_format)

            worksheet.autofilter(0, 0, len(rows) - 1, len(header) - 1)

    def _view_in_browser(self, rows: list[list[str]]) -> None:
        from workpytools.common.browser_preview import write_and_open

        html = _render_html_table(rows)
        write_and_open(html, "workpytools_profiler_preview.html", no_open=False)


def _render_html_table(rows: list[list[str]]) -> str:
    import html as html_module

    header, *data_rows = rows
    bad_cols = {i for i, h in enumerate(header) if h in ("is_filled", "is_unique")}

    head_html = "".join(f"<th>{html_module.escape(h)}</th>" for h in header)
    body_html = []
    for row in data_rows:
        cells = []
        for i, value in enumerate(row):
            cls = ' class="bad"' if i in bad_cols and value == "False" else ""
            cells.append(f"<td{cls}>{html_module.escape(value)}</td>")
        body_html.append(f"<tr>{''.join(cells)}</tr>")

    style = """\
:root { color-scheme: light dark; }
body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 1.5rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #999; padding: 0.3rem 0.6rem; text-align: left; }
th { position: sticky; top: 0; background: #eee; }
td.bad { background: #ffdcdc; }
@media (prefers-color-scheme: dark) {
  body { background: #1e1e1e; color: #ddd; }
  th { background: #333; }
  td.bad { background: #5a2a2a; }
  th, td { border-color: #555; }
}
"""

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<title>profiler result</title>
<style>{style}</style>
</head>
<body>
<table>
<thead><tr>{head_html}</tr></thead>
<tbody>{"".join(body_html)}</tbody>
</table>
</body>
</html>
"""
