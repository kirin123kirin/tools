from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import win32clipboard
import win32con
from PIL import Image, ImageGrab

from workpytools.common.textfile import (
    TextFileError,
    normalize_newlines,
    read_text_with_fallback,
)

SourceKind = Literal["path", "clipboard_file", "clipboard_data", "clipboard_text"]


class ClipboardImageError(RuntimeError):
    """Raised when no usable image can be obtained from the clipboard."""


class ClipboardTextError(RuntimeError):
    """Raised when no usable text can be obtained from the clipboard."""


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


@dataclass(frozen=True)
class LoadedText:
    """Text plus where it came from. Mirrors `LoadedImage` for text-based commands."""

    text: str
    source_path: Path | None
    source_kind: SourceKind


def _normalize_newlines(text: str) -> str:
    return normalize_newlines(text)


def _read_text_file(path: Path, encoding: str | None) -> str:
    """Read a text file, re-raising as ClipboardTextError for this module's callers."""
    try:
        return read_text_with_fallback(path, encoding)
    except TextFileError as exc:
        raise ClipboardTextError(str(exc)) from exc


def load_text(path: str | Path | None, encoding: str | None = None) -> LoadedText:
    """Load text from a file path, or from the Windows clipboard if `path` is None.

    Clipboard input covers two cases:
    - plain text (e.g. copied from a text editor)
    - a copied file object (e.g. Ctrl+C on a file in Explorer), read as text

    `encoding` forces a specific codec (no fallback) when reading a file;
    `None` tries UTF-8 (with BOM support) then falls back to CP932.
    """
    if path is not None:
        resolved = Path(path)
        text = _read_text_file(resolved, encoding)
        return LoadedText(
            text=_normalize_newlines(text), source_path=resolved, source_kind="path"
        )

    win32clipboard.OpenClipboard()
    try:
        has_files = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP)
        has_text = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT)
        if has_files:
            files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
        elif has_text:
            clip_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        else:
            raise ClipboardTextError("クリップボードにテキストがありません")
    finally:
        win32clipboard.CloseClipboard()

    if has_files:
        if not files:
            raise ClipboardTextError("クリップボードにファイルがありません")
        resolved = Path(files[0])
        text = _read_text_file(resolved, encoding)
        return LoadedText(
            text=_normalize_newlines(text), source_path=resolved, source_kind="clipboard_file"
        )

    return LoadedText(
        text=_normalize_newlines(clip_text), source_path=None, source_kind="clipboard_text"
    )


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


def _build_dibv5(image: Image.Image) -> bytes:
    """Build a BITMAPV5HEADER + 32bpp BGRA pixel buffer for CF_DIBV5.

    CF_DIB (BITMAPINFOHEADER) has no alpha channel, so `touka`'s transparent
    output would otherwise lose its transparency (Pillow's RGB conversion
    fills transparent pixels with black) once round-tripped through the
    clipboard. CF_DIBV5 carries an explicit alpha mask, which apps like
    PowerPoint/Word honor on paste.
    """
    rgba = image.convert("RGBA")
    width, height = rgba.size

    # DIBの行は下から上へ格納する（Windowsのボトムアップ規約）
    flipped = rgba.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    r, g, b, a = flipped.split()
    bgra = Image.merge("RGBA", (b, g, r, a))
    pixels = bgra.tobytes()

    header = struct.pack(
        "<IiiHHIIiiII",
        124,  # bV5Size
        width,  # bV5Width
        height,  # bV5Height
        1,  # bV5Planes
        32,  # bV5BitCount
        3,  # bV5Compression = BI_BITFIELDS
        len(pixels),  # bV5SizeImage
        0,  # bV5XPelsPerMeter
        0,  # bV5YPelsPerMeter
        0,  # bV5ClrUsed
        0,  # bV5ClrImportant
    )
    header += struct.pack(
        "<IIII",
        0x00FF0000,  # bV5RedMask
        0x0000FF00,  # bV5GreenMask
        0x000000FF,  # bV5BlueMask
        0xFF000000,  # bV5AlphaMask
    )
    header += struct.pack("<i", 0x73524742)  # bV5CSType = LCS_sRGB
    header += b"\x00" * 36  # bV5Endpoints（LCS_sRGBでは無視されるフィールド、ゼロ埋め）
    header += struct.pack("<III", 0, 0, 0)  # bV5GammaRed/Green/Blue
    header += struct.pack("<I", 4)  # bV5Intent = LCS_GM_IMAGES
    header += struct.pack("<III", 0, 0, 0)  # bV5ProfileData/Size/Reserved

    return header + pixels


def _build_dib(image: Image.Image) -> bytes:
    """Build a BITMAPINFOHEADER + 24bpp BGR pixel buffer for CF_DIB (no alpha).

    Transparent pixels are flattened onto a white background, since CF_DIB
    has no alpha channel and apps that only read CF_DIB would otherwise get
    Pillow's black-fill behavior from a plain RGBA->RGB conversion.
    """
    rgba = image.convert("RGBA")
    width, height = rgba.size

    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.split()[3])
    flipped = background.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    r, g, b = flipped.split()
    bgr = Image.merge("RGB", (b, g, r))
    row_bytes = width * 3
    padding = (4 - row_bytes % 4) % 4
    if padding:
        pixels = b"".join(
            bgr.tobytes()[i : i + row_bytes] + b"\x00" * padding
            for i in range(0, len(bgr.tobytes()), row_bytes)
        )
    else:
        pixels = bgr.tobytes()

    header = struct.pack(
        "<IiiHHIIiiII",
        40,  # biSize (BITMAPINFOHEADER)
        width,
        height,
        1,  # biPlanes
        24,  # biBitCount
        0,  # biCompression = BI_RGB
        len(pixels),  # biSizeImage
        0,  # biXPelsPerMeter
        0,  # biYPelsPerMeter
        0,  # biClrUsed
        0,  # biClrImportant
    )
    return header + pixels


def _png_clipboard_format() -> int:
    """The "PNG" clipboard format ID is not a fixed constant; look it up at runtime.

    Browsers (Chrome/Firefox) and Office apps (PowerPoint/Word) prefer this
    format when pasting an image, since it carries alpha unambiguously as a
    literal PNG byte stream rather than a DIB variant. Without it, apps that
    don't understand CF_DIBV5's alpha semantics may silently ignore the
    paste (no error, nothing happens).
    """
    return int(win32clipboard.RegisterClipboardFormat("PNG"))


def copy_image_to_clipboard(image: Image.Image) -> None:
    """Put image data on the clipboard in three formats, as if via "Copy Image":

    - "PNG" (custom format, raw PNG bytes): what PowerPoint/Word/browsers
      prefer for pasting; carries alpha unambiguously.
    - CF_DIBV5: alpha-aware DIB, for apps that don't read the "PNG" format
      but do understand BITMAPV5HEADER.
    - CF_DIB: alpha-flattened (white background) 24bpp DIB, for apps that
      only understand the classic BITMAPINFOHEADER format.
    """
    rgba = image.convert("RGBA")
    with io.BytesIO() as buf:
        rgba.save(buf, "PNG")
        png_bytes = buf.getvalue()

    dibv5 = _build_dibv5(rgba)
    dib = _build_dib(rgba)

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(_png_clipboard_format(), png_bytes)
        win32clipboard.SetClipboardData(win32con.CF_DIBV5, dibv5)
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()


def _cf_html_format() -> int:
    """The CF_HTML format ID is not a fixed constant; it must be looked up at runtime."""
    return int(win32clipboard.RegisterClipboardFormat("HTML Format"))


def has_clipboard_html() -> bool:
    win32clipboard.OpenClipboard()
    try:
        return bool(win32clipboard.IsClipboardFormatAvailable(_cf_html_format()))
    finally:
        win32clipboard.CloseClipboard()


def has_clipboard_text() -> bool:
    win32clipboard.OpenClipboard()
    try:
        return bool(win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT))
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_text() -> str:
    """Read CF_UNICODETEXT from the clipboard, raising if not available."""
    win32clipboard.OpenClipboard()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            raise ClipboardTextError("クリップボードにテキストがありません")
        return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_html_fragment() -> str:
    """Read CF_HTML from the clipboard and return just the fragment between
    <!--StartFragment--> and <!--EndFragment-->, falling back to the header
    byte offsets if the comment markers are missing or the offsets are stale.
    """
    win32clipboard.OpenClipboard()
    try:
        fmt = _cf_html_format()
        if not win32clipboard.IsClipboardFormatAvailable(fmt):
            raise ClipboardTextError("クリップボードにHTMLがありません")
        raw = win32clipboard.GetClipboardData(fmt)
    finally:
        win32clipboard.CloseClipboard()

    raw_bytes = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
    text = raw_bytes.decode("utf-8", errors="replace")

    start_marker = "<!--StartFragment-->"
    end_marker = "<!--EndFragment-->"
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    if start_idx != -1 and end_idx != -1:
        return text[start_idx + len(start_marker) : end_idx]

    # コメントマーカーが見つからない場合、ヘッダーのバイトオフセットにフォールバックする
    headers: dict[str, int] = {}
    for line in text.split("\r\n"):
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key in ("StartFragment", "EndFragment"):
            try:
                headers[key] = int(value)
            except ValueError:
                continue
        if len(headers) == 2:
            break

    if "StartFragment" not in headers or "EndFragment" not in headers:
        raise ClipboardTextError("CF_HTMLのヘッダーを解析できません")

    return raw_bytes[headers["StartFragment"] : headers["EndFragment"]].decode(
        "utf-8", errors="replace"
    )


def _build_cf_html(html_fragment: str) -> bytes:
    """Wrap an HTML fragment in the CF_HTML header format (byte offsets, UTF-8)."""
    header_template = (
        "Version:0.9\r\n"
        "StartHTML:{:010d}\r\n"
        "EndHTML:{:010d}\r\n"
        "StartFragment:{:010d}\r\n"
        "EndFragment:{:010d}\r\n"
    )
    header_len = len(header_template.format(0, 0, 0, 0).encode("utf-8"))

    prefix = "<html><body>\r\n<!--StartFragment-->"
    suffix = "<!--EndFragment-->\r\n</body></html>"

    start_html = header_len
    start_fragment = start_html + len(prefix.encode("utf-8"))
    end_fragment = start_fragment + len(html_fragment.encode("utf-8"))
    end_html = end_fragment + len(suffix.encode("utf-8"))

    header = header_template.format(start_html, end_html, start_fragment, end_fragment)
    return (header + prefix + html_fragment + suffix).encode("utf-8")


def copy_html_and_text_to_clipboard(html_fragment: str, plain_text: str) -> None:
    """Put both CF_HTML and CF_UNICODETEXT on the clipboard in one session.

    Rich-text-aware apps (Outlook/Word/Slack) read CF_HTML for styled paste;
    plain-text-only apps fall back to CF_UNICODETEXT.
    """
    html_data = _build_cf_html(html_fragment)

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(_cf_html_format(), html_data)
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, plain_text)
    finally:
        win32clipboard.CloseClipboard()


def copy_text_to_clipboard(text: str) -> None:
    """Put plain text on the clipboard (CF_UNICODETEXT only)."""
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
