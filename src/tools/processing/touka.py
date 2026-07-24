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

    Input source is auto-detected, and the default output location follows
    whichever of the three it was:
    - `path` given: read that image file (jpg/png/...); output defaults next
      to it as `{stem}_touka.png`
    - `path` omitted, clipboard holds a copied file (e.g. Ctrl+C on a file in
      Explorer): output defaults next to that source file, same as above
    - `path` omitted, clipboard holds raw image data (e.g. "Copy Image" in a
      viewer): no source file exists, so output defaults to a timestamped
      file in the current directory
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
        loaded = load_image(args.path)
        logger.info("background removal starting (size=%s)", loaded.image.size)

        result = remove(loaded.image)

        output_path = (
            Path(args.output) if args.output else self._default_output_path(loaded.source_path)
        )
        result.save(output_path)
        print(output_path)
        return 0

    @staticmethod
    def _default_output_path(source_path: Path | None) -> Path:
        if source_path is not None:
            return source_path.with_name(f"{source_path.stem}_touka.png")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return Path.cwd() / f"clipboard_touka_{timestamp}.png"
