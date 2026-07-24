from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageGrab


class ClipboardImageError(RuntimeError):
    """Raised when no usable image can be obtained from the clipboard."""


def load_image(path: str | Path | None) -> Image.Image:
    """Load an image from a file path, or from the Windows clipboard if `path` is None.

    Clipboard input covers two cases:
    - raw image data (e.g. copied via "Copy Image" in a browser/viewer)
    - a copied file object (e.g. Ctrl+C on a file in Explorer), which Pillow
      reports as a list of file paths on Windows.
    """
    if path is not None:
        return Image.open(path).convert("RGBA")

    clip = ImageGrab.grabclipboard()
    if clip is None:
        raise ClipboardImageError("クリップボードに画像データがありません")
    if isinstance(clip, list):
        if not clip:
            raise ClipboardImageError("クリップボードにファイルがありません")
        return Image.open(clip[0]).convert("RGBA")
    return clip.convert("RGBA")
