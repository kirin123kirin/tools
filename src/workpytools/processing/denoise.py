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

_DEFAULT_H_COLOR = 10.0
_DEFAULT_TEMPLATE_WINDOW_SIZE = 7
_DEFAULT_SEARCH_WINDOW_SIZE = 21


class DenoiseProcessor(Processor):
    """Remove photographic grain / sensor noise using OpenCV Non-local Means Denoising.

    Input source and default output location follow the same convention as
    touka: explicit `path` or a file copied in Explorer saves next to (or,
    for the clipboard-file case, into the OS temp dir and back onto the
    clipboard as) `{stem}_denoised.png`; raw clipboard image data skips the
    file and is placed directly on the clipboard as image data.
    """

    name = "denoise"
    help = "画像のノイズ除去（ファイルパス／クリップボード入力対応、OpenCV Non-local Means）"

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
            "-s",
            "--strength",
            type=float,
            default=10.0,
            help="ノイズ除去強度 h（デフォルト: 10.0）。"
            "値を大きくするほどノイズは減るがディテールも失われる",
        )

    def run(self, args: argparse.Namespace) -> int:
        loaded = load_image(args.path)
        logger.info("denoise starting (size=%s, strength=%s)", loaded.image.size, args.strength)

        result = self._denoise(loaded.image, h=args.strength)

        output_path = save_result(loaded, result, "denoised", args.output)
        print(describe_output(output_path))
        return 0

    @staticmethod
    def _denoise(image: Image.Image, h: float) -> Image.Image:
        """Apply fastNlMeansDenoisingColored, preserving the original alpha channel untouched."""
        rgba = np.array(image)
        rgb = rgba[:, :, :3]
        alpha = rgba[:, :, 3]

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        denoised_bgr = cv2.fastNlMeansDenoisingColored(
            bgr,
            None,
            h=h,
            hColor=_DEFAULT_H_COLOR,
            templateWindowSize=_DEFAULT_TEMPLATE_WINDOW_SIZE,
            searchWindowSize=_DEFAULT_SEARCH_WINDOW_SIZE,
        )
        denoised_rgb = cv2.cvtColor(denoised_bgr, cv2.COLOR_BGR2RGB)

        out = np.dstack([denoised_rgb, alpha])
        return Image.fromarray(out, mode="RGBA")
