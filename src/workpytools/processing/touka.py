from __future__ import annotations

import argparse
import logging

from rembg import remove

from workpytools.common.clipboard import load_image
from workpytools.common.output import describe_output, save_result
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)


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

    def run(self, args: argparse.Namespace) -> int:
        loaded = load_image(args.path)
        logger.info("background removal starting (size=%s)", loaded.image.size)

        result = remove(loaded.image)

        output_path = save_result(loaded, result, "touka", args.output)
        print(describe_output(output_path))
        return 0
