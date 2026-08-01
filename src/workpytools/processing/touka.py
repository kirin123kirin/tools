from __future__ import annotations

import argparse
import logging

from rembg import remove

from workpytools.common.clipboard import load_image
from workpytools.common.output import describe_output, save_result
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_DEFAULT_ALPHA_MATTING_FOREGROUND_THRESHOLD = 240
_DEFAULT_ALPHA_MATTING_BACKGROUND_THRESHOLD = 10
_DEFAULT_ALPHA_MATTING_ERODE_SIZE = 10


class ToukaProcessor(Processor):
    """Remove the background from an image, producing a transparent PNG.

    Input source is auto-detected, and the default output location follows
    whichever of the three it was:
    - `path` given: read that image file (jpg/png/...); output defaults next
      to it as `{stem}_touka.png`
    - `path` omitted, clipboard holds a copied file (e.g. Ctrl+C on a file in
      Explorer): output is saved under the OS temp dir as `{stem}_touka.png`
      and the file is placed on the clipboard, ready to paste
    - `path` omitted, clipboard holds raw image data (e.g. "Copy Image" in a
      viewer): no file is written; the processed image is placed on the
      clipboard as raw image data, ready to paste
    """

    name = "touka"
    help = "画像の背景を透過する（ファイルパス／クリップボード入力対応）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            default=None,
            help="画像ファイルパス。省略時はクリップボードの画像/コピーしたファイルを使用",
        )
        parser.add_argument(
            "-o", "--output", default=None, help="出力先パス（省略時は自動生成、拡張子はpng）"
        )
        parser.add_argument(
            "-a",
            "--alpha-matting",
            action="store_true",
            help="アルファマッティングを有効にする。髪の毛など細かい輪郭の透過精度が上がるが、"
            "処理が遅くなる",
        )
        parser.add_argument(
            "-F",
            "--alpha-matting-foreground-threshold",
            type=int,
            default=_DEFAULT_ALPHA_MATTING_FOREGROUND_THRESHOLD,
            help=f"アルファマッティングの前景しきい値（0-255、既定"
            f"{_DEFAULT_ALPHA_MATTING_FOREGROUND_THRESHOLD}）。--alpha-matting指定時のみ有効",
        )
        parser.add_argument(
            "-B",
            "--alpha-matting-background-threshold",
            type=int,
            default=_DEFAULT_ALPHA_MATTING_BACKGROUND_THRESHOLD,
            help=f"アルファマッティングの背景しきい値（0-255、既定"
            f"{_DEFAULT_ALPHA_MATTING_BACKGROUND_THRESHOLD}）。--alpha-matting指定時のみ有効",
        )
        parser.add_argument(
            "-E",
            "--alpha-matting-erode-size",
            type=int,
            default=_DEFAULT_ALPHA_MATTING_ERODE_SIZE,
            help=f"アルファマッティングの侵食サイズ（既定{_DEFAULT_ALPHA_MATTING_ERODE_SIZE}）。"
            "--alpha-matting指定時のみ有効",
        )
        parser.add_argument(
            "-c",
            "--bgcolor",
            type=int,
            nargs=4,
            metavar=("R", "G", "B", "A"),
            default=None,
            help="背景を透過せず指定色(RGBA、各0-255)で塗りつぶす。省略時は透過のまま",
        )
        parser.add_argument(
            "-m",
            "--only-mask",
            action="store_true",
            help="前景/背景の二値マスク画像のみを出力する（切り抜き結果ではなくマスクそのもの）",
        )
        parser.add_argument(
            "-p",
            "--post-process-mask",
            action="store_true",
            help="マスクにノイズ除去・穴埋めの後処理を適用する",
        )

    def run(self, args: argparse.Namespace) -> int:
        loaded = load_image(args.path)
        logger.info("background removal starting (size=%s)", loaded.image.size)

        bgcolor = tuple(args.bgcolor) if args.bgcolor is not None else None
        result = remove(
            loaded.image,
            alpha_matting=args.alpha_matting,
            alpha_matting_foreground_threshold=args.alpha_matting_foreground_threshold,
            alpha_matting_background_threshold=args.alpha_matting_background_threshold,
            alpha_matting_erode_size=args.alpha_matting_erode_size,
            only_mask=args.only_mask,
            post_process_mask=args.post_process_mask,
            bgcolor=bgcolor,
        )

        output_path = save_result(loaded, result, "touka", args.output)
        print(describe_output(output_path))
        return 0
