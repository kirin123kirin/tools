from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import win32clipboard
import win32con
from PIL import Image, ImageGrab

SourceKind = Literal["path", "clipboard_file", "clipboard_data"]


class ClipboardImageError(RuntimeError):
    """Raised when no usable image can be obtained from the clipboard."""


@dataclass(frozen=True)
class LoadedImage:
    """An image plus where it came from.

    `source_kind` distinguishes the three supported input patterns:
    - "path": an explicit file path argument
    - "clipboard_file": clipboard holds a copied file object (e.g. Ctrl+C on
      a file in Explorer)
    - "clipboard_data": clipboard holds raw image data with no file behind
      it (e.g. "Copy Image" in a viewer)

    `source_path` is set for "path" and "clipboard_file" (a real file exists),
    and is `None` for "clipboard_data".
    """

    image: Image.Image
    source_path: Path | None
    source_kind: SourceKind


def load_image(path: str | Path | None) -> LoadedImage:
    """Load an image from a file path, or from the Windows clipboard if `path` is None.

    Clipboard input covers two cases:
    - raw image data (e.g. copied via "Copy Image" in a browser/viewer)
    - a copied file object (e.g. Ctrl+C on a file in Explorer), which Pillow
      reports as a list of file paths on Windows.
    """
    if path is not None:
        resolved = Path(path)
        return LoadedImage(
            image=Image.open(resolved).convert("RGBA"), source_path=resolved, source_kind="path"
        )

    clip = ImageGrab.grabclipboard()
    if clip is None:
        raise ClipboardImageError("クリップボードに画像データがありません")
    if isinstance(clip, list):
        if not clip:
            raise ClipboardImageError("クリップボードにファイルがありません")
        resolved = Path(clip[0])
        return LoadedImage(
            image=Image.open(resolved).convert("RGBA"),
            source_path=resolved,
            source_kind="clipboard_file",
        )
    return LoadedImage(image=clip.convert("RGBA"), source_path=None, source_kind="clipboard_data")


def copy_file_to_clipboard(path: Path) -> None:
    """Put a file object on the clipboard (CF_HDROP), as if copied in Explorer.

    Lets the user paste the resulting file with Ctrl+V into Explorer, Outlook,
    Slack, etc.
    """
    path_str = str(path.resolve())
    # DROPFILES構造体 + ダブルNUL終端のファイルパス列（CF_HDROPの仕様）
    dropfiles = struct.pack("Iiiii", 20, 0, 0, 0, 0)
    data = dropfiles + path_str.encode("utf-16-le") + b"\x00\x00\x00\x00"

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
    finally:
        win32clipboard.CloseClipboard()


def copy_image_to_clipboard(image: Image.Image) -> None:
    """Put raw image data on the clipboard (CF_DIB), as if via "Copy Image"."""
    with io.BytesIO() as buf:
        image.convert("RGB").save(buf, "BMP")
        # BMPファイルヘッダー（先頭14バイト）を除いたDIB部分のみがCF_DIBの中身
        dib = buf.getvalue()[14:]

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()
