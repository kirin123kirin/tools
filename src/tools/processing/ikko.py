from __future__ import annotations

import argparse
import logging

from tools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from tools.common.shape_cluster import (
    LEFT_TOLERANCE,
    LINE_STEP_MAX_RATIO,
    LINE_STEP_MIN_RATIO,
    ShapeInfo,
    cluster_shapes,
)
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes


class IkkoProcessor(Processor):
    """Merge adjacent single-line text boxes on the current slide (or the
    current selection) into one multi-paragraph text box. Meant for
    PowerPoint's "convert to shapes" output, which splits each line of a
    paragraph into its own text box.
    """

    name = "ikko"
    help = "スライド上のバラバラなテキストボックスを1つに合体する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際には変更せず、合体対象になるクラスタを表示するだけにする",
        )
        parser.add_argument(
            "--left-tolerance",
            type=float,
            default=LEFT_TOLERANCE,
            help=f"左端座標の許容誤差（ポイント、既定{LEFT_TOLERANCE}）",
        )
        parser.add_argument(
            "--line-step-min",
            type=float,
            default=LINE_STEP_MIN_RATIO,
            help=f"行送りの下限（フォントサイズ比、既定{LINE_STEP_MIN_RATIO}）",
        )
        parser.add_argument(
            "--line-step-max",
            type=float,
            default=LINE_STEP_MAX_RATIO,
            help=f"行送りの上限（フォントサイズ比、既定{LINE_STEP_MAX_RATIO}）",
        )

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
            com_shapes = self._resolve_target_shapes(app)
        except Exception as exc:
            raise SystemExit(f"対象範囲の取得中にエラーが発生しました: {exc}") from exc

        shape_infos = [
            info for info in (self._to_shape_info(s) for s in com_shapes) if info is not None
        ]

        if not shape_infos:
            print("対象になるテキストボックスがありません")
            return 0

        clusters = [c for c in cluster_shapes(
            shape_infos,
            left_tolerance=args.left_tolerance,
            line_step_min_ratio=args.line_step_min,
            line_step_max_ratio=args.line_step_max,
        ) if len(c) >= 2]

        if not clusters:
            print("合体できる組み合わせが見つかりませんでした（--left-tolerance等のオプションで閾値を調整できます）")
            return 0

        if args.dry_run:
            self._print_dry_run(clusters)
            return 0

        try:
            app.StartNewUndoEntry()
            merged_count = 0
            removed_count = 0
            for cluster in clusters:
                self._merge_cluster(cluster)
                merged_count += 1
                removed_count += len(cluster) - 1
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info("合体したクラスタ数=%d 削除したシェイプ数=%d", merged_count, removed_count)
        total_before = removed_count + merged_count
        print(f"{merged_count}個のクラスタを合体しました（{total_before}個のシェイプを{merged_count}個に）")
        return 0

    def _resolve_target_shapes(self, app: object) -> list[object]:
        selection = app.ActiveWindow.Selection  # type: ignore[attr-defined]
        if selection.Type == _SELECTION_SHAPES:
            shape_range = selection.ShapeRange
            return [shape_range.Item(i) for i in range(1, shape_range.Count + 1)]

        slide = app.ActiveWindow.View.Slide  # type: ignore[attr-defined]
        return [slide.Shapes.Item(i) for i in range(1, slide.Shapes.Count + 1)]

    def _to_shape_info(self, shape: object) -> ShapeInfo | None:
        if not getattr(shape, "HasTextFrame", False):
            return None
        text_range = shape.TextFrame.TextRange  # type: ignore[attr-defined]
        text = text_range.Text
        if not text or not text.strip():
            return None
        if text_range.Paragraphs().Count != 1:
            return None

        font = text_range.Font
        try:
            color = font.Color.RGB
        except Exception:
            color = None

        if font.Name is None or font.Size is None:
            return None

        return ShapeInfo(
            left=shape.Left,  # type: ignore[attr-defined]
            top=shape.Top,  # type: ignore[attr-defined]
            width=shape.Width,  # type: ignore[attr-defined]
            height=shape.Height,  # type: ignore[attr-defined]
            text=text,
            font_name=font.Name,
            font_size=font.Size,
            bold=font.Bold,
            color=color,
            alignment=text_range.ParagraphFormat.Alignment,
            ref=shape,
        )

    def _print_dry_run(self, clusters: list[list[ShapeInfo]]) -> None:
        for i, cluster in enumerate(clusters, start=1):
            print(f"クラスタ{i}: {len(cluster)}個のシェイプ")
            for info in cluster:
                print(f"  Left={info.left:.1f} Top={info.top:.1f} Text={info.text!r}")

    def _merge_cluster(self, cluster: list[ShapeInfo]) -> None:
        lefts = [c.left for c in cluster]
        tops = [c.top for c in cluster]
        rights = [c.left + c.width for c in cluster]
        bottoms = [c.top + c.height for c in cluster]

        new_left = min(lefts)
        new_top = min(tops)
        new_width = max(rights) - new_left
        new_height = max(bottoms) - new_top

        style = cluster[0]
        base_shape = cluster[0].ref
        lines = [c.text for c in cluster]

        text_range = base_shape.TextFrame.TextRange  # type: ignore[attr-defined]
        text_range.Text = "\r".join(lines)

        if style.font_name is not None:
            text_range.Font.Name = style.font_name
        if style.font_size is not None:
            text_range.Font.Size = style.font_size
        if style.bold is not None:
            text_range.Font.Bold = style.bold
        if style.color is not None:
            text_range.Font.Color.RGB = style.color
        if style.alignment is not None:
            text_range.ParagraphFormat.Alignment = style.alignment

        base_shape.Left = new_left  # type: ignore[attr-defined]
        base_shape.Top = new_top  # type: ignore[attr-defined]
        base_shape.Width = new_width  # type: ignore[attr-defined]
        base_shape.Height = new_height  # type: ignore[attr-defined]

        for info in cluster[1:]:
            info.ref.Delete()  # type: ignore[attr-defined]
