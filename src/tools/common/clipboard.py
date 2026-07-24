from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageGrab


class ClipboardImageError(RuntimeError):
    """Raised when no usable image can be obtained from the clipboard."""


@dataclass(frozen=True)
class LoadedImage:
    """An image plus, when known, the file path it originated from.

    `source_path` is set for input patterns that have a real file behind
    them (an explicit path argument, or a file copied in Explorer), and is
    `None` for raw clipboard image data (e.g. "Copy Image" in a viewer),
    which has no file of its own. Callers use this to decide where a
    result should default to being saved.
    """

    image: Image.Image
    source_path: Path | None


def load_image(path: str | Path | None) -> LoadedImage:
    """Load an image from a file path, or from the Windows clipboard if `path` is None.

    Clipboard input covers two cases:
    - raw image data (e.g. copied via "Copy Image" in a browser/viewer)
    - a copied file object (e.g. Ctrl+C on a file in Explorer), which Pillow
      reports as a list of file paths on Windows.
    """
    if path is not None:
        resolved = Path(path)
        return LoadedImage(image=Image.open(resolved).convert("RGBA"), source_path=resolved)

    clip = ImageGrab.grabclipboard()
    if clip is None:
        raise ClipboardImageError("クリップボードに画像データがありません")
    if isinstance(clip, list):
        if not clip:
            raise ClipboardImageError("クリップボードにファイルがありません")
        resolved = Path(clip[0])
        return LoadedImage(image=Image.open(resolved).convert("RGBA"), source_path=resolved)
    return LoadedImage(image=clip.convert("RGBA"), source_path=None)
