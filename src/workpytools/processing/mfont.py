from __future__ import annotations

import argparse
import logging

from workpytools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_MSO_GROUP = 6  # msoGroup
_DEFAULT_FONT = "メイリオ"


class MfontProcessor(Processor):
    """Set the Japanese (far-east) font to Meiryo across the whole
    presentation: the theme's font scheme, every placeholder on every
    slide master/layout, and every shape's text on every slide (recursing
    into groups). Latin (non far-east) fonts are left untouched.

    Tables and SmartArt/embedded objects aren't walked -- only shapes with
    a text frame (HasTextFrame) are touched.
    """

    name = "mfont"
    help = "テーマ・スライドマスター・全スライドの和文フォントをメイリオに統一する"

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
            app.StartNewUndoEntry()
            theme_changed = self._apply_theme_fonts(presentation)
            master_shapes = self._apply_masters(presentation)
            slide_shapes = self._apply_slides(presentation)
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "テーマ変更=%s マスター内シェイプ数=%d スライド内シェイプ数=%d",
            theme_changed,
            master_shapes,
            slide_shapes,
        )
        print(
            f"和文フォントを{_DEFAULT_FONT}に統一しました"
            f"（テーマ、マスター{master_shapes}件、スライド{slide_shapes}件）"
        )
        return 0

    def _apply_theme_fonts(self, presentation: object) -> bool:
        # 複数デザイン（セクションごとに別テーマ等）を使っている場合に備え、
        # SlideMasterだけでなくDesigns配下の全マスターのテーマを対象にする
        changed = False
        for design in presentation.Designs:  # type: ignore[attr-defined]
            theme = design.SlideMaster.Theme
            font_scheme = theme.ThemeFontScheme
            font_scheme.MajorFont.NameFarEast = _DEFAULT_FONT
            font_scheme.MinorFont.NameFarEast = _DEFAULT_FONT
            changed = True
        return changed

    def _apply_masters(self, presentation: object) -> int:
        count = 0
        for design in presentation.Designs:  # type: ignore[attr-defined]
            master = design.SlideMaster
            count += self._apply_shapes(master.Shapes)
            for layout in master.CustomLayouts:
                count += self._apply_shapes(layout.Shapes)
        return count

    def _apply_slides(self, presentation: object) -> int:
        count = 0
        for slide in presentation.Slides:  # type: ignore[attr-defined]
            count += self._apply_shapes(slide.Shapes)
        return count

    def _apply_shapes(self, shapes: object) -> int:
        count = 0
        for i in range(1, shapes.Count + 1):  # type: ignore[attr-defined]
            shape = shapes.Item(i)  # type: ignore[attr-defined]
            count += self._apply_shape(shape)
        return count

    def _apply_shape(self, shape: object) -> int:
        count = 0
        if getattr(shape, "Type", None) == _MSO_GROUP:
            count += self._apply_shapes(shape.GroupItems)  # type: ignore[attr-defined]
            return count

        if not getattr(shape, "HasTextFrame", False):
            return count

        text_range = shape.TextFrame.TextRange  # type: ignore[attr-defined]
        if not text_range.Text:
            return count

        text_range.Font.NameFarEast = _DEFAULT_FONT
        return count + 1
