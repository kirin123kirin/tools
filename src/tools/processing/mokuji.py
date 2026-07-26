from __future__ import annotations

import argparse
import logging
import re

from tools.common.clipboard import copy_text_to_clipboard
from tools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from tools.common.textfile import to_crlf
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_NEWLINE_RE = re.compile(r"\r\n|\r|\n")


class MokujiProcessor(Processor):
    """Collect a title per slide across the active presentation and copy
    the list to the clipboard, one title per line.
    """

    name = "mokuji"
    help = "全スライドのタイトルを一覧化してクリップボードにコピーする"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        try:
            app = get_running_powerpoint()
        except PowerPointNotRunningError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            presentation = get_active_presentation(app)
        except NoActivePresentationError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            slide_count = presentation.Slides.Count
            if slide_count == 0:
                print("対象のスライドがありません")
                return 0

            titles = [
                self._extract_title(presentation.Slides.Item(i))
                for i in range(1, slide_count + 1)
            ]
        except Exception as exc:
            raise SystemExit(f"PowerPointの操作中にエラーが発生しました: {exc}") from exc

        text = to_crlf("\n".join(titles))
        copy_text_to_clipboard(text)
        logger.info("%d枚のスライドから%d件のタイトルを抽出しました", slide_count, len(titles))
        print(f"{len(titles)}件のタイトルをコピーしました")
        return 0

    def _extract_title(self, slide: object) -> str:
        if slide.Shapes.HasTitle:  # type: ignore[attr-defined]
            title_text = slide.Shapes.Title.TextFrame.TextRange.Text  # type: ignore[attr-defined]
            if title_text.strip():
                return self._flatten(title_text)

        fallback = self._topmost_text(slide)
        return self._flatten(fallback) if fallback else ""

    def _topmost_text(self, slide: object) -> str | None:
        best_top: float | None = None
        best_text: str | None = None
        for shape in slide.Shapes:  # type: ignore[attr-defined]
            if not getattr(shape, "HasTextFrame", False):
                continue
            text = shape.TextFrame.TextRange.Text
            if not text or not text.strip():
                continue
            if best_top is None or shape.Top < best_top:
                best_top = shape.Top
                best_text = text
        return best_text

    def _flatten(self, text: str) -> str:
        return _NEWLINE_RE.sub(" ", text).strip()
