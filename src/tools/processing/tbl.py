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
    GAP_RATIO,
    GRID_TOLERANCE,
    DuplicateGridPositionError,
    GridShape,
    compute_spaced_positions,
    estimate_grid,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes
_MSO_SHAPE_RECTANGLE = 1
_BORDER_SIDES = (1, 2, 3, 4)  # ppBorderTop/Left/Bottom/Right


class TblProcessor(Processor):
    """Convert between a PowerPoint table and a matrix of independent
    shapes, and split a single multi-line text shape into one shape per
    line. The direction is inferred from the current selection:

    - selection contains a table            -> decompose (table -> rects)
    - 2+ shapes selected, no table          -> compose (rects -> table)
    - exactly 1 shape, multi-line text      -> line-split
    - anything else (incl. nothing selected) -> error or no-op, see run()
    """

    name = "tbl"
    help = "PowerPointの表とシェイプ群を相互変換する（表分解/表合成/行分割）"

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
            raise SystemExit("対象を選択してから実行してください")

        shape_range = selection.ShapeRange
        selected = [shape_range.Item(i) for i in range(1, shape_range.Count + 1)]

        tables = [s for s in selected if getattr(s, "HasTable", False)]

        if tables:
            return self._run_decompose(app, tables)

        if len(selected) >= 2:
            return self._run_compose(app, selected)

        if len(selected) == 1:
            return self._run_line_split(app, selected[0])

        raise SystemExit("対象を選択してから実行してください")

    # --- 分解: 表 -> 四角形群 ---

    def _run_decompose(self, app: object, tables: list[object]) -> int:
        try:
            app.StartNewUndoEntry()  # type: ignore[attr-defined]
            total_shapes = 0
            for table_shape in tables:
                total_shapes += self._decompose_one_table(table_shape)
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info("分解した表の数=%d 作成した四角形数=%d", len(tables), total_shapes)
        print(f"{len(tables)}個の表を分解しました（合計{total_shapes}個の四角形に）")
        return 0

    def _decompose_one_table(self, table_shape: object) -> int:
        table = table_shape.Table  # type: ignore[attr-defined]
        n_rows = table.Rows.Count
        n_cols = table.Columns.Count
        slide = table_shape.Parent  # type: ignore[attr-defined]

        col_widths = [table.Columns(c).Width for c in range(1, n_cols + 1)]
        row_heights = [table.Rows(r).Height for r in range(1, n_rows + 1)]
        col_offsets = compute_spaced_positions(col_widths, GAP_RATIO)
        row_offsets = compute_spaced_positions(row_heights, GAP_RATIO)

        table_left = table_shape.Left  # type: ignore[attr-defined]
        table_top = table_shape.Top  # type: ignore[attr-defined]

        created = 0
        for r in range(1, n_rows + 1):
            for c in range(1, n_cols + 1):
                cell = table.Cell(r, c)
                cell_shape = cell.Shape
                new_left = table_left + col_offsets[c - 1][0]
                new_top = table_top + row_offsets[r - 1][0]
                width = col_widths[c - 1]
                height = row_heights[r - 1]

                rect = slide.Shapes.AddShape(
                    _MSO_SHAPE_RECTANGLE, new_left, new_top, width, height
                )
                self._apply_cell_style(cell, cell_shape, rect, r, c)
                created += 1

        table_shape.Delete()  # type: ignore[attr-defined]
        return created

    def _apply_cell_style(
        self, cell: object, cell_shape: object, rect: object, row: int, col: int
    ) -> None:
        text_range = cell_shape.TextFrame.TextRange  # type: ignore[attr-defined]
        rect.TextFrame.TextRange.Text = text_range.Text  # type: ignore[attr-defined]

        font = text_range.Font
        rect_font = rect.TextFrame.TextRange.Font  # type: ignore[attr-defined]
        if font.Name is not None:
            rect_font.Name = font.Name
        if font.Size is not None:
            rect_font.Size = font.Size
        if font.Bold is not None:
            rect_font.Bold = font.Bold
        try:
            rect_font.Color.RGB = font.Color.RGB
        except Exception:
            pass
        try:
            rect.TextFrame.TextRange.ParagraphFormat.Alignment = (  # type: ignore[attr-defined]
                text_range.ParagraphFormat.Alignment
            )
        except Exception:
            pass

        try:
            fill = cell_shape.Fill  # type: ignore[attr-defined]
            rect.Fill.Visible = fill.Visible  # type: ignore[attr-defined]
            if fill.Visible:
                rect.Fill.ForeColor.RGB = fill.ForeColor.RGB  # type: ignore[attr-defined]
        except Exception:
            pass

        self._apply_borders(cell, rect, row, col)

    def _apply_borders(self, cell: object, rect: object, row: int, col: int) -> None:
        try:
            borders = [cell.Borders(side) for side in _BORDER_SIDES]  # type: ignore[attr-defined]
            weights = [b.Weight for b in borders]
            colors = [b.ForeColor.RGB for b in borders]
            visibles = [b.Visible for b in borders]
        except Exception:
            return

        uniform = (
            len(set(weights)) == 1 and len(set(colors)) == 1 and len(set(visibles)) == 1
        )
        if not uniform:
            logger.warning(
                "セル(%d,%d)の罫線が辺ごとに異なるため、上辺の値で統一しました", row, col
            )

        rect.Line.Weight = weights[0]  # type: ignore[attr-defined]
        rect.Line.ForeColor.RGB = colors[0]  # type: ignore[attr-defined]
        rect.Line.Visible = visibles[0]  # type: ignore[attr-defined]

    # --- 合成: 四角形群 -> 表 ---

    def _run_compose(self, app: object, shapes: list[object]) -> int:
        grid_shapes = [
            GridShape(
                left=s.Left,  # type: ignore[attr-defined]
                top=s.Top,  # type: ignore[attr-defined]
                width=s.Width,  # type: ignore[attr-defined]
                height=s.Height,  # type: ignore[attr-defined]
                ref=s,
            )
            for s in shapes
        ]

        try:
            positions, n_rows, n_cols = estimate_grid(grid_shapes, GRID_TOLERANCE)
        except DuplicateGridPositionError as exc:
            raise SystemExit(str(exc)) from exc

        missing = n_rows * n_cols - len(positions)
        if missing:
            logger.warning("歯抜けのグリッド位置: %d件", missing)

        slide = shapes[0].Parent  # type: ignore[attr-defined]

        overall_left = min(s.left for s in grid_shapes)
        overall_top = min(s.top for s in grid_shapes)
        overall_right = max(s.left + s.width for s in grid_shapes)
        overall_bottom = max(s.top + s.height for s in grid_shapes)

        try:
            app.StartNewUndoEntry()  # type: ignore[attr-defined]
            table_shape = slide.Shapes.AddTable(
                n_rows,
                n_cols,
                overall_left,
                overall_top,
                overall_right - overall_left,
                overall_bottom - overall_top,
            )
            table = table_shape.Table

            col_widths: dict[int, float] = {}
            row_heights: dict[int, float] = {}
            for pos in positions:
                col_widths.setdefault(pos.col, pos.shape.width)
                row_heights.setdefault(pos.row, pos.shape.height)
                self._copy_shape_to_cell(pos.shape.ref, table.Cell(pos.row + 1, pos.col + 1))

            for col, width in col_widths.items():
                table.Columns(col + 1).Width = width
            for row, height in row_heights.items():
                table.Rows(row + 1).Height = height

            for shape in shapes:
                shape.Delete()  # type: ignore[attr-defined]
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "推定グリッド=%d行%d列 対象シェイプ数=%d 歯抜け=%d",
            n_rows,
            n_cols,
            len(shapes),
            missing,
        )
        print(f"{len(shapes)}個のシェイプを1個の表（{n_rows}行{n_cols}列）に合成しました")
        return 0

    def _copy_shape_to_cell(self, shape: object, cell: object) -> None:
        cell_shape = cell.Shape  # type: ignore[attr-defined]
        cell_shape.TextFrame.TextRange.Text = shape.TextFrame.TextRange.Text  # type: ignore[attr-defined]

        font = shape.TextFrame.TextRange.Font  # type: ignore[attr-defined]
        cell_font = cell_shape.TextFrame.TextRange.Font
        if font.Name is not None:
            cell_font.Name = font.Name
        if font.Size is not None:
            cell_font.Size = font.Size
        if font.Bold is not None:
            cell_font.Bold = font.Bold

        try:
            fill = shape.Fill  # type: ignore[attr-defined]
            cell_shape.Fill.Visible = fill.Visible
            if fill.Visible:
                cell_shape.Fill.ForeColor.RGB = fill.ForeColor.RGB
        except Exception:
            pass

        try:
            line = shape.Line  # type: ignore[attr-defined]
            for side in _BORDER_SIDES:
                border = cell.Borders(side)  # type: ignore[attr-defined]
                border.Weight = line.Weight
                border.ForeColor.RGB = line.ForeColor.RGB
                border.Visible = line.Visible
        except Exception:
            pass

    # --- 行分割: 複数行テキスト -> 行ごとのシェイプ ---

    def _run_line_split(self, app: object, shape: object) -> int:
        if not getattr(shape, "HasTextFrame", False):
            print("変換対象がありません")
            return 0

        text_range = shape.TextFrame.TextRange  # type: ignore[attr-defined]
        if not text_range.Text or not text_range.Text.strip():
            print("変換対象がありません")
            return 0

        lines_range = text_range.Lines()
        line_count = lines_range.Count
        if line_count <= 1:
            print("変換対象がありません")
            return 0

        lines = []
        for i in range(1, line_count + 1):
            line = text_range.Lines(i, 1)
            text = line.Text.rstrip("\r")
            if text.strip():
                lines.append((text, line.Font))

        skipped = line_count - len(lines)
        if skipped:
            logger.info("空行をスキップしました: %d件", skipped)

        if not lines:
            print("変換対象がありません")
            return 0

        slide = shape.Parent  # type: ignore[attr-defined]
        left = shape.Left  # type: ignore[attr-defined]
        width = shape.Width  # type: ignore[attr-defined]
        line_height = shape.Height / len(lines)  # type: ignore[attr-defined]
        offsets = compute_spaced_positions([line_height] * len(lines), GAP_RATIO)
        top = shape.Top  # type: ignore[attr-defined]

        try:
            app.StartNewUndoEntry()  # type: ignore[attr-defined]
            for (text, font), (offset, _gap) in zip(lines, offsets, strict=True):
                new_box = slide.Shapes.AddTextbox(1, left, top + offset, width, line_height)
                new_range = new_box.TextFrame.TextRange
                new_range.Text = text
                if font.Name is not None:
                    new_range.Font.Name = font.Name
                if font.Size is not None:
                    new_range.Font.Size = font.Size
                if font.Bold is not None:
                    new_range.Font.Bold = font.Bold
                try:
                    new_range.Font.Color.RGB = font.Color.RGB
                except Exception:
                    pass

            shape.Delete()  # type: ignore[attr-defined]
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info("分割した行数=%d スキップした空行数=%d", len(lines), skipped)
        print(f"1個のテキストを{len(lines)}行のシェイプに分割しました")
        return 0
