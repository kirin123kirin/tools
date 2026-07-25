from __future__ import annotations

import argparse
import logging
import re

from tools.common.clipboard import copy_text_to_clipboard, get_clipboard_text
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

# 引用の入れ子(`>`の繰り返し)とインデントを保ったまま、行頭の箇条書き記号 */+ を捉える。
_BULLET_RE = re.compile(r"^((?:>\s*)*)([ \t]*)([*+])(\s+)(.*)$")


def _is_horizontal_rule(line: str) -> bool:
    """`* * *` / `- - -` / `___` などのCommonMark水平線かどうか。"""
    stripped = line.strip()
    if not stripped:
        return False
    without_spaces = stripped.replace(" ", "")
    chars = set(without_spaces)
    if len(chars) != 1:
        return False
    ch = next(iter(chars))
    if ch not in "*-_":
        return False
    return len(without_spaces) >= 3


def normalize_bullet_markers(text: str) -> tuple[str, bool]:
    """Rewrite leading `*`/`+` bullet markers to `-` so mdformat treats a
    hand-typed mixed-marker list as one list instead of splitting it into
    alternating adjacent lists. Returns (rewritten_text, changed).

    Code fences and indented code blocks are left untouched; horizontal
    rules (`* * *`) and emphasis (`**bold**`, `*italic*`) are not mistaken
    for bullets.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    changed = False
    prev_line_is_list_item = False

    for line in lines:
        stripped_left = line.lstrip()

        if stripped_left.startswith("```") or stripped_left.startswith("~~~"):
            in_fence = not in_fence
            out.append(line)
            prev_line_is_list_item = False
            continue
        if in_fence:
            out.append(line)
            continue

        if not line.strip():
            out.append(line)
            continue

        leading_spaces = len(line) - len(line.lstrip(" "))
        if leading_spaces >= 4 and not prev_line_is_list_item:
            # インデントコードブロックの可能性が高いため触らない
            out.append(line)
            prev_line_is_list_item = False
            continue

        if _is_horizontal_rule(line):
            out.append(line)
            prev_line_is_list_item = False
            continue

        match = _BULLET_RE.match(line)
        if match:
            quote_prefix, indent, marker, spacing, rest = match.groups()
            if marker != "-":
                changed = True
            out.append(f"{quote_prefix}{indent}-{spacing}{rest}")
            prev_line_is_list_item = True
            continue

        out.append(line)
        prev_line_is_list_item = False

    return "\n".join(out), changed


def format_markdown(text: str) -> str:
    import mdformat

    result: str = mdformat.text(text, extensions={"tables"})
    return result


class ClipfmtProcessor(Processor):
    """Format the clipboard's Markdown text (mdformat) and write it back.

    Always reads CF_UNICODETEXT (CF_HTML, if present, is ignored) and writes
    only CF_UNICODETEXT back -- formatting doesn't change the document's
    format, so there's nothing rich-text-specific to set.
    """

    name = "clipfmt"
    help = "クリップボードのMarkdownを整形する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--no-normalize-bullets",
            action="store_true",
            help="箇条書き記号(*/+)を-に統一する前処理を行わない",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            source_text = get_clipboard_text()
        except Exception as exc:
            raise SystemExit("整形対象のテキストがありません") from exc

        text_to_format = source_text
        if not args.no_normalize_bullets:
            text_to_format, bullets_changed = normalize_bullet_markers(source_text)
            if bullets_changed:
                logger.info("箇条書き記号を - に統一しました")

        try:
            formatted = format_markdown(text_to_format)
        except Exception as exc:
            raise SystemExit(
                f"Markdownの整形に失敗しました（クリップボードは変更していません）: {exc}"
            ) from exc

        if not formatted.strip():
            raise SystemExit("整形結果が空です")

        if formatted == source_text:
            logger.info("整形の必要はありませんでした（既に整形済みです）")
        else:
            logger.info("整形により内容が変わりました")

        copy_text_to_clipboard(formatted)
        print("整形しました")
        return 0
