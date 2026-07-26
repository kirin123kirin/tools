from __future__ import annotations

import argparse
import logging

from tools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from tools.common.table_shapes import (
    GRID_TOLERANCE,
    DuplicateGridPositionError,
    GridShape,
    column_and_row_sizes,
    estimate_grid,
    grid_centers,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes


class SeiretsuProcessor(Processor):
    """Realign selected shapes into a grid by position only. Unlike tbl's
    compose direction, this never creates a table or deletes/creates
    shapes -- each shape keeps its size, text, and formatting; only
    Left/Top are rewritten so shapes' centers land on grid positions.
    """

    name = "seiretsu"
    help = "選択したシェイプを表に変換せず格子状の位置に整列する"

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

        grid_shapes = [
            GridShape(left=s.Left, top=s.Top, width=s.Width, height=s.Height, ref=s)
            for s in shapes
        ]

        try:
            positions, n_rows, n_cols = estimate_grid(grid_shapes, GRID_TOLERANCE)
        except DuplicateGridPositionError as exc:
            raise SystemExit(str(exc)) from exc

        missing = n_rows * n_cols - len(positions)
        if missing:
            logger.warning("歯抜けのグリッド位置: %d件", missing)

        col_width, row_height = column_and_row_sizes(positions, n_rows, n_cols)

        overall_left = min(s.left for s in grid_shapes)
        overall_top = min(s.top for s in grid_shapes)

        center_x, center_y = grid_centers(col_width, row_height, overall_left, overall_top)

        try:
            app.StartNewUndoEntry()
            for pos in positions:
                shape = pos.shape.ref
                new_left = center_x[pos.col] - pos.shape.width / 2
                new_top = center_y[pos.row] - pos.shape.height / 2
                shape.Left = new_left  # type: ignore[attr-defined]
                shape.Top = new_top  # type: ignore[attr-defined]
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "対象シェイプ数=%d 推定グリッド=%d行%d列 歯抜け=%d",
            len(shapes),
            n_rows,
            n_cols,
            missing,
        )
        print(f"{len(shapes)}個のシェイプを{n_rows}行{n_cols}列に整列しました")
        return 0
