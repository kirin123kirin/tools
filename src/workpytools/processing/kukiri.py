from __future__ import annotations

import argparse
import logging

import cv2
import numpy as np
from PIL import Image

from workpytools.common.clipboard import load_image
from workpytools.common.output import describe_output, save_result
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_BILATERAL_DIAMETER = 9
_UNSHARP_BLUR_SIGMA = 3.0


class KukiriProcessor(Processor):
    """Clean up JPEG edge bleeding/ringing and sharpen boundaries.

    Intended for flat-design illustrations where JPEG compression has
    blurred/smudged the boundary between flat color regions. Applies an
    edge-preserving bilateral filter (smooths within regions, leaves edges
    intact) followed by an unsharp mask (boosts edge contrast).

    Input source and default output location follow the same convention as
    touka/denoise: explicit `path` or a file copied in Explorer saves next
    to (or, for the clipboard-file case, into the OS temp dir and back onto
    the clipboard as) `{stem}_kukiri.png`; raw clipboard image data skips
    the file and is placed directly on the clipboard as image data.
    """

    name = "kukiri"
    help = "JPEGの輪郭滲みを除去し境界をくっきりさせる（フラットイラスト向け）"

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
            "--smooth",
            type=float,
            default=75.0,
            help="バイラテラルフィルタの強さ（デフォルト: 75.0）。"
            "大きいほど滲みは消えるが細部も失われる",
        )
        parser.add_argument(
            "--sharpen",
            type=float,
            default=0.5,
            help="アンシャープマスクの強さ（デフォルト: 0.5、0で無効）。"
            "大きいほど境界のコントラストが強調される",
        )

    def run(self, args: argparse.Namespace) -> int:
        loaded = load_image(args.path)
        logger.info(
            "kukiri starting (size=%s, smooth=%s, sharpen=%s)",
            loaded.image.size,
            args.smooth,
            args.sharpen,
        )

        result = self._process(loaded.image, smooth=args.smooth, sharpen=args.sharpen)

        output_path = save_result(loaded, result, "kukiri", args.output)
        print(describe_output(output_path))
        return 0

    @staticmethod
    def _process(image: Image.Image, smooth: float, sharpen: float) -> Image.Image:
        """Bilateral-filter then unsharp-mask, preserving the alpha channel untouched."""
        rgba = np.array(image)
        rgb = rgba[:, :, :3]
        alpha = rgba[:, :, 3]

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        smoothed = cv2.bilateralFilter(
            bgr, d=_BILATERAL_DIAMETER, sigmaColor=smooth, sigmaSpace=smooth
        )
        blurred = cv2.GaussianBlur(smoothed, (0, 0), sigmaX=_UNSHARP_BLUR_SIGMA)
        sharpened = cv2.addWeighted(smoothed, 1 + sharpen, blurred, -sharpen, 0)

        result_rgb = cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB)
        out = np.dstack([result_rgb, alpha])
        return Image.fromarray(out, mode="RGBA")
