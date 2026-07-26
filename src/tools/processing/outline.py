from __future__ import annotations

import argparse
import logging

from tools.common.clipboard import ClipboardTextError, get_clipboard_text
from tools.common.outline_parse import OutlineItem, parse_outline
from tools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_LAYOUT_TITLE_AND_CONTENT = 2  # ppLayoutText


class OutlineProcessor(Processor):
    """Turn a clipboard outline into slides appended to the active
    PowerPoint presentation. Only adds slides -- table-of-contents
    generation is a separate command (mokuji).
    """

    name = "outline"
    help = "クリップボードのアウトラインからPowerPointにスライドを追加する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        try:
            text = get_clipboard_text()
        except ClipboardTextError as exc:
            raise SystemExit(str(exc)) from exc

        items = parse_outline(text)
        if not items:
            raise SystemExit("アウトラインとして解釈できる内容がありません")

        presentation, created_new = self._get_or_create_presentation()

        try:
            for item in items:
                self._add_slide(presentation, item)
        except Exception as exc:
            raise SystemExit(f"PowerPointの操作中にエラーが発生しました: {exc}") from exc

        logger.info(
            "%d件のスライドを追加しました（%s）",
            len(items),
            "新規プレゼンテーション" if created_new else "既存のプレゼンテーションに追記",
        )
        print(f"{len(items)}件のスライドを追加しました")
        return 0

    def _get_or_create_presentation(self) -> tuple[object, bool]:
        try:
            app = get_running_powerpoint()
        except PowerPointNotRunningError:
            import win32com.client

            app = win32com.client.Dispatch("PowerPoint.Application")
            app.Visible = True
            presentation = app.Presentations.Add()
            logger.info("PowerPointを新規起動し、新規プレゼンテーションを作成しました")
            return presentation, True

        try:
            presentation = get_active_presentation(app)
        except NoActivePresentationError:
            presentation = app.Presentations.Add()
            logger.info("既存のPowerPointに新規プレゼンテーションを作成しました")
            return presentation, True

        logger.info("既存のプレゼンテーションに追記します")
        return presentation, False

    def _add_slide(self, presentation: object, item: OutlineItem) -> None:
        index = presentation.Slides.Count + 1  # type: ignore[attr-defined]
        slide = presentation.Slides.Add(index, _LAYOUT_TITLE_AND_CONTENT)  # type: ignore[attr-defined]
        slide.Shapes.Placeholders(1).TextFrame.TextRange.Text = item.title
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = item.body.replace("\n", "\r")
