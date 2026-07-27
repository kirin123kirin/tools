from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from workpytools.common.clipboard import copy_text_to_clipboard
from workpytools.common.walk import Entry, compute_total_sizes, dedupe_by_fullpath, walk
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_DEFAULT_EXCLUDE = (".git", ".svn", "node_modules", "__pycache__")
_UNIT_DIVISORS = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}


def _format_size(size: int | None, unit: str) -> str:
    if size is None:
        return ""
    if unit == "b":
        return str(size)
    value = size / _UNIT_DIVISORS[unit]
    return f"{value:.2f}"


def _resolve_link(fullpath: str) -> str:
    """Resolve a .lnk shortcut target via WScript.Shell (a public COM API),
    not by parsing the .lnk binary format ourselves.
    """
    import win32com.client

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(fullpath)
        return str(shortcut.TargetPath)
    except Exception as exc:
        logger.warning("ショートカットの解決に失敗しました: %s (%s)", fullpath, exc)
        return ""


class LsdirProcessor(Processor):
    """List files and directories under one or more roots as a flat table,
    suitable for sorting/filtering in Excel. Column count is fixed for a
    given invocation (no variable-length directory nesting columns).
    """

    name = "lsdir"
    help = "フォルダ配下をExcelで集計できる表形式で一覧化する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("path", nargs="+", help="対象フォルダ（複数・グロブ可）")
        parser.add_argument("-o", "--output", default=None, help="出力先パス（.tsv / .xlsx）")
        parser.add_argument("--clip", action="store_true", help="結果をクリップボードにコピーする")
        parser.add_argument(
            "--files-only", action="store_true", help="ファイルのみ出力する"
        )
        parser.add_argument(
            "--dirs-only", action="store_true", help="フォルダのみ出力する"
        )
        parser.add_argument(
            "--exclude",
            nargs="+",
            default=list(_DEFAULT_EXCLUDE),
            help="除外するフォルダ名（既定: %(default)s）",
        )
        parser.add_argument(
            "--include-temp",
            action="store_true",
            help="'~$'で始まる一時ファイルも含める",
        )
        parser.add_argument(
            "--total-size",
            action="store_true",
            help="フォルダ配下の合計サイズを計算する（全走査後に出力するため待ち時間が発生する）",
        )
        parser.add_argument(
            "--unit",
            choices=["b", "kb", "mb", "gb"],
            default="kb",
            help="サイズの単位（既定: kb）",
        )
        parser.add_argument(
            "--resolve-link",
            action="store_true",
            help=".lnkのリンク先を解決する（WScript.Shell経由、大量にあると遅くなる）",
        )
        parser.add_argument(
            "--encoding",
            default="cp932" if os.name == "nt" else "utf-8",
            help="出力エンコーディング",
        )

    def run(self, args: argparse.Namespace) -> int:
        roots = self._resolve_roots(args.path)

        all_entries: list[Entry] = []
        total_skipped_dirs = 0
        for root, source_label in roots:
            entries, skipped = walk(
                root,
                source_label,
                exclude=frozenset(args.exclude),
                include_temp=args.include_temp,
            )
            all_entries.extend(entries)
            total_skipped_dirs += skipped

        if total_skipped_dirs:
            logger.warning("アクセスできず読み飛ばしたフォルダ: %d件", total_skipped_dirs)

        all_entries, dup_skipped = dedupe_by_fullpath(all_entries)
        if dup_skipped:
            logger.info("起点の重複により除外したエントリ: %d件", dup_skipped)

        # ファイル行を落とす前に合計サイズを計算する必要がある
        # （--dirs-only 指定時、ファイルのサイズ情報がないと配下の合計が出せない）。
        total_sizes = compute_total_sizes(all_entries) if args.total_size else {}

        if args.files_only:
            all_entries = [e for e in all_entries if e.type == "file"]
        elif args.dirs_only:
            all_entries = [e for e in all_entries if e.type == "dir"]

        link_by_path: dict[str, str] = {}
        if args.resolve_link:
            for entry in all_entries:
                if entry.ext.lower() == ".lnk":
                    link_by_path[entry.fullpath] = _resolve_link(entry.fullpath)

        header = ["source", "type", "name", "fullpath", "parent", "ext", "size", "mtime", "depth"]
        if args.resolve_link:
            header.append("link")

        rows = [header]
        for entry in all_entries:
            if args.total_size and entry.type == "dir":
                size_value: int | None = total_sizes.get(entry.fullpath, 0)
            else:
                size_value = entry.size

            row = [
                entry.source,
                entry.type,
                entry.name,
                entry.fullpath,
                entry.parent,
                entry.ext,
                _format_size(size_value, args.unit),
                entry.mtime,
                str(entry.depth),
            ]
            if args.resolve_link:
                row.append(link_by_path.get(entry.fullpath, ""))
            rows.append(row)

        self._emit(rows, args)
        return 0

    def _resolve_roots(self, patterns: list[str]) -> list[tuple[str, str]]:
        from glob import glob

        roots = []
        for pattern in patterns:
            matches = glob(pattern) or [pattern]
            for match in matches:
                path = Path(match)
                if not path.exists():
                    raise SystemExit(f"指定したパスが存在しません: {path}")
                roots.append((str(path), match))
        return roots

    def _emit(self, rows: list[list[str]], args: argparse.Namespace) -> None:
        tsv_text = "\n".join("\t".join(row) for row in rows)

        if args.clip:
            copy_text_to_clipboard(tsv_text)
            print("一覧をコピーしました")
            return

        if args.output:
            self._write_output(rows, tsv_text, args.output, args.encoding)
            return

        print(tsv_text)

    def _write_output(
        self, rows: list[list[str]], tsv_text: str, output: str, encoding: str
    ) -> None:
        output_path = Path(output)
        if output_path.suffix.lower() == ".xlsx":
            self._write_excel(rows, output_path)
        else:
            output_path.write_bytes(
                tsv_text.encode(encoding, errors="backslashreplace")
            )
        logger.info("一覧を書き出しました: %s", output_path)
        print(output_path)

    def _write_excel(self, rows: list[list[str]], output_path: Path) -> None:
        import xlsxwriter

        header = rows[0]
        size_col = header.index("size") if "size" in header else None

        with xlsxwriter.Workbook(str(output_path)) as workbook:
            worksheet = workbook.add_worksheet("lsdir")
            header_format = workbook.add_format({"bold": True, "border": 1})
            worksheet.write_row(0, 0, header, header_format)

            for r, row in enumerate(rows[1:], start=1):
                for c, value in enumerate(row):
                    if c == size_col and value:
                        worksheet.write_number(r, c, float(value))
                    else:
                        worksheet.write(r, c, value)

            worksheet.autofilter(0, 0, len(rows) - 1, len(header) - 1)
