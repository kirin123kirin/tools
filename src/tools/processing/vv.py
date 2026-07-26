from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from tools.common.clipboard import copy_text_to_clipboard
from tools.common.config import ConfigLocationError, vv_prompts_dir
from tools.common.textfile import (
    TextFileError,
    display_width,
    pad_to_width,
    read_text_with_fallback,
    to_crlf,
    truncate_to_width,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_PREVIEW_WIDTH = 46


@dataclass(frozen=True)
class Prompt:
    name: str
    path: Path


def list_prompts(prompts_dir: Path) -> list[Prompt]:
    """Collect prompt .txt files directly under `prompts_dir`, sorted by file name.

    Extension matching is case-insensitive (Windows filesystems don't
    distinguish case, and glob's behavior there isn't guaranteed), and the
    result is explicitly sorted rather than relying on iteration order.
    """
    if not prompts_dir.is_dir():
        return []

    files = [
        entry
        for entry in prompts_dir.iterdir()
        if entry.is_file() and entry.name.lower().endswith(".txt")
    ]
    files.sort(key=lambda p: p.name)
    return [Prompt(name=p.stem, path=p) for p in files]


def _first_non_blank_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def format_prompt_list(prompts: list[Prompt]) -> list[str]:
    """Render the numbered list, aligning columns by display width.

    Alignment uses display width rather than `len()` because Japanese names
    render twice as wide as their character count, which would otherwise
    leave the preview column ragged.
    """
    number_width = len(str(len(prompts)))
    name_width = max((display_width(p.name) for p in prompts), default=0)

    lines: list[str] = []
    for index, prompt in enumerate(prompts, start=1):
        try:
            body = read_text_with_fallback(prompt.path)
            preview = truncate_to_width(_first_non_blank_line(body), _PREVIEW_WIDTH)
        except (TextFileError, OSError):
            # 一覧表示は他のプロンプトが見えることを優先し、読めないものは印だけ付ける
            preview = "(読み込めません)"

        number = str(index).rjust(number_width)
        if preview:
            lines.append(f"{number}: {pad_to_width(prompt.name, name_width)}  {preview}")
        else:
            lines.append(f"{number}: {prompt.name}")

    return lines


class VvProcessor(Processor):
    """Copy a saved prompt to the clipboard, ready to paste with Ctrl+V.

    Running with no argument only lists what's available (it never touches
    the clipboard); passing a number copies that prompt immediately without
    printing the list, which is the "one keystroke" path.
    """

    name = "vv"
    help = "定型プロンプトをクリップボードにコピーする（引数なしで一覧表示）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "number",
            nargs="?",
            default=None,
            help="コピーするプロンプトの番号。省略時は一覧を表示するだけ",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            prompts_dir = vv_prompts_dir()
        except ConfigLocationError as exc:
            raise SystemExit(str(exc)) from exc

        prompts = list_prompts(prompts_dir)
        if not prompts:
            raise SystemExit(
                f"プロンプトが登録されていません。{prompts_dir} に .txt を置いてください"
            )

        if args.number is None:
            for line in format_prompt_list(prompts):
                print(line)
            return 0

        index = self._parse_number(args.number, len(prompts))
        prompt = prompts[index - 1]

        try:
            body = read_text_with_fallback(prompt.path)
        except TextFileError as exc:
            raise SystemExit(str(exc)) from exc
        except OSError as exc:
            raise SystemExit(f"ファイルを読み込めません: {prompt.path}") from exc

        logger.info("プロンプトを読み込みました: %s", prompt.path)
        copy_text_to_clipboard(to_crlf(body))
        print(f"コピーしました: {prompt.name}")
        return 0

    def _parse_number(self, raw: str, count: int) -> int:
        try:
            number = int(raw)
        except ValueError as exc:
            raise SystemExit(
                f"番号は数値で指定してください（1〜{count} の範囲）: {raw!r}"
            ) from exc

        if not 1 <= number <= count:
            raise SystemExit(f"番号は 1〜{count} の範囲で指定してください: {number}")

        return number
