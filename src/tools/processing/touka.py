from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from rembg import remove

from tools.common.clipboard import load_image
from tools.processing.base import Processor

logger = logging.getLogger(__name__)


class ToukaProcessor(Processor):
    """Remove the background from an image, producing a transparent PNG.

    Input source is auto-detected:
    - `path` given: read that image file (jpg/png/...)
    - `path` omitted: read from the clipboard (raw image data, or a copied
      file object such as Ctrl+C on a file in Explorer)
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

    def run(self, args: argparse.Namespace) -> int:
        image = load_image(args.path)
        logger.info("background removal starting (size=%s)", image.size)

        result = remove(image)

        output_path = Path(args.output) if args.output else self._default_output_path(args.path)
        result.save(output_path)
        print(output_path)
        return 0

    @staticmethod
    def _default_output_path(path: str | None) -> Path:
        if path:
            src = Path(path)
            return src.with_name(f"{src.stem}_touka.png")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return Path.cwd() / f"clipboard_touka_{timestamp}.png"
