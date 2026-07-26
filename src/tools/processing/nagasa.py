from __future__ import annotations

import argparse
import logging

from tools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes
_PP_AUTO_SIZE_NONE = 0


class NagasaProcessor(Processor):
    """Unify the width and height of selected shapes to the max found
    among them, resizing around each shape's own center so relative
    positions (e.g. after seiretsu) aren't disturbed.
    """

    name = "nagasa"
    help = "選択したシェイプの幅・高さを最大値に統一する"

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
            get_active_presentation(app)
        except NoActivePresentationError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            selection = app.ActiveWindow.Selection
        except Exception as exc:
            raise SystemExit(f"選択状態の取得中にエラーが発生しました: {exc}") from exc

        if selection.Type != _SELECTION_SHAPES:
            raise SystemExit("対象を選択してから実行してください（2つ以上選択が必要です）")

        shape_range = selection.ShapeRange
        shapes = [shape_range.Item(i) for i in range(1, shape_range.Count + 1)]

        if len(shapes) < 2:
            raise SystemExit("対象を選択してから実行してください（2つ以上選択が必要です）")

        max_width = max(s.Width for s in shapes)
        max_height = max(s.Height for s in shapes)

        try:
            app.StartNewUndoEntry()
            for shape in shapes:
                self._disable_autosize(shape)
                center_x = shape.Left + shape.Width / 2
                center_y = shape.Top + shape.Height / 2
                shape.Width = max_width
                shape.Height = max_height
                shape.Left = center_x - max_width / 2
                shape.Top = center_y - max_height / 2
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "対象シェイプ数=%d 統一サイズ=幅%.1f 高さ%.1f", len(shapes), max_width, max_height
        )
        print(
            f"{len(shapes)}個のシェイプのサイズを統一しました"
            f"（幅{max_width:.1f}pt, 高さ{max_height:.1f}pt）"
        )
        return 0

    def _disable_autosize(self, shape: object) -> None:
        if not getattr(shape, "HasTextFrame", False):
            return
        try:
            shape.TextFrame.AutoSize = _PP_AUTO_SIZE_NONE  # type: ignore[attr-defined]
        except Exception:
            pass
