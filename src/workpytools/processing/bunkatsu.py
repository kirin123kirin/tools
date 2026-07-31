from __future__ import annotations

import argparse
import logging
import tempfile
import uuid
from pathlib import Path

from PIL import Image

from workpytools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from workpytools.common.watershed import DEFAULT_DISTANCE_RATIO, split_regions
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes
_MSO_PICTURE = 13  # msoPicture
_MSO_LINKED_PICTURE = 11  # msoLinkedPicture
_PP_SHAPE_FORMAT_PNG = 2  # ppShapeFormatPNG


class BunkatsuProcessor(Processor):
    """Split a selected picture shape on the current slide into its
    separate objects using marker-based watershed segmentation, replacing
    it with one transparent-PNG picture shape per detected region at the
    same position/scale.

    Only picture shapes (`msoPicture`/`msoLinkedPicture`) are supported.
    Requires exactly one shape selected. A single Undo entry covers the
    whole operation, so Ctrl+Z restores the original picture in one step.
    """

    name = "bunkatsu"
    help = "選択中の画像シェイプを物体ごとに領域分割し、個別の画像として再配置する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--distance-ratio",
            type=float,
            default=DEFAULT_DISTANCE_RATIO,
            help=(
                "分割の厳しさ（0-1、既定"
                f"{DEFAULT_DISTANCE_RATIO}）。値を上げるほど接触した物体を分割"
                "しやすくなる一方、単一物体を過分割するリスクが増える"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際には変更せず、検出される領域数だけを表示する",
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
            selection = app.ActiveWindow.Selection
        except Exception as exc:
            raise SystemExit(f"選択状態の取得中にエラーが発生しました: {exc}") from exc

        if selection.Type != _SELECTION_SHAPES or selection.ShapeRange.Count != 1:
            raise SystemExit("画像シェイプを1つ選択してから実行してください")

        shape = selection.ShapeRange.Item(1)
        if shape.Type not in (_MSO_PICTURE, _MSO_LINKED_PICTURE):
            raise SystemExit("選択されているシェイプは画像ではありません")

        left, top, width, height = shape.Left, shape.Top, shape.Width, shape.Height

        tmp_path = Path(tempfile.gettempdir()) / f"workpytools_bunkatsu_{uuid.uuid4().hex}.png"
        try:
            shape.Export(str(tmp_path), _PP_SHAPE_FORMAT_PNG)
            with Image.open(tmp_path) as opened:
                source_image = opened.copy()
        finally:
            tmp_path.unlink(missing_ok=True)

        regions = split_regions(source_image, distance_ratio=args.distance_ratio)

        if len(regions) < 2:
            print("分割できる領域が見つかりませんでした（物体は1つ、または検出できませんでした）")
            return 0

        if args.dry_run:
            print(f"{len(regions)}個の領域に分割されます（実際には変更していません）")
            return 0

        slide = shape.Parent
        source_width_px, source_height_px = source_image.size
        scale_x = width / source_width_px
        scale_y = height / source_height_px

        try:
            app.StartNewUndoEntry()
            region_paths = self._save_regions(regions)
            try:
                for region_path, region, offset_x_px, offset_y_px in region_paths:
                    new_shape = slide.Shapes.AddPicture(
                        str(region_path),
                        LinkToFile=False,
                        SaveWithDocument=True,
                        Left=left + offset_x_px * scale_x,
                        Top=top + offset_y_px * scale_y,
                        Width=region.width * scale_x,
                        Height=region.height * scale_y,
                    )
                    new_shape.Name = f"{shape.Name}_bunkatsu"
            finally:
                for region_path, _region, _ox, _oy in region_paths:
                    region_path.unlink(missing_ok=True)

            shape.Delete()
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info("分割数=%d", len(regions))
        print(f"{len(regions)}個の画像に分割しました")
        return 0

    def _save_regions(
        self, regions: list[Image.Image]
    ) -> list[tuple[Path, Image.Image, int, int]]:
        """Save each region to a temp PNG, returning (path, region, offset_x_px, offset_y_px).

        Offsets are the region's crop origin relative to the source image,
        in source-image pixels (converted to slide points by the caller).
        """
        saved: list[tuple[Path, Image.Image, int, int]] = []
        for i, region in enumerate(regions):
            filename = f"workpytools_bunkatsu_region_{uuid.uuid4().hex}_{i}.png"
            path = Path(tempfile.gettempdir()) / filename
            region.save(path)
            offset_x = region.info.get("offset_x", 0)
            offset_y = region.info.get("offset_y", 0)
            saved.append((path, region, offset_x, offset_y))
        return saved
