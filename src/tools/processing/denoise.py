from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from tools.common.clipboard import load_image
from tools.processing.base import Processor

logger = logging.getLogger(__name__)

_DEFAULT_H_COLOR = 10.0
_DEFAULT_TEMPLATE_WINDOW_SIZE = 7
_DEFAULT_SEARCH_WINDOW_SIZE = 21


class DenoiseProcessor(Processor):
    """Remove photographic grain / sensor noise using OpenCV Non-local Means Denoising.

    Input source is auto-detected (same convention as touka):
    - `path` given: read that image file
    - `path` omitted: read from the clipboard (raw image data, or a copied
      file object such as Ctrl+C on a file in Explorer)
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
            "--strength",
            type=float,
            default=10.0,
            help="ノイズ除去強度 h（デフォルト: 10.0）。"
            "値を大きくするほどノイズは減るがディテールも失われる",
        )

    def run(self, args: argparse.Namespace) -> int:
        image = load_image(args.path)
        logger.info("denoise starting (size=%s, strength=%s)", image.size, args.strength)

        result = self._denoise(image, h=args.strength)

        output_path = Path(args.output) if args.output else self._default_output_path(args.path)
        result.save(output_path)
        print(output_path)
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

    @staticmethod
    def _default_output_path(path: str | None) -> Path:
        if path:
            src = Path(path)
            return src.with_name(f"{src.stem}_denoised.png")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return Path.cwd() / f"clipboard_denoised_{timestamp}.png"
