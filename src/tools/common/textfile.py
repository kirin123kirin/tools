from __future__ import annotations

import unicodedata
from pathlib import Path


class TextFileError(RuntimeError):
    """Raised when a text file can't be read with any supported encoding."""


def normalize_newlines(text: str) -> str:
    """Normalize CRLF / CR line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def to_crlf(text: str) -> str:
    """Convert line endings to CRLF, the Windows clipboard convention.

    Normalizes to LF first so that already-CRLF input doesn't become CR CRLF.
    """
    return normalize_newlines(text).replace("\n", "\r\n")


def read_text_with_fallback(path: Path, encoding: str | None = None) -> str:
    """Read a text file as UTF-8 (BOM tolerated), falling back to CP932.

    Japanese Windows files are commonly CP932, so a UTF-8-only read would fail
    on files written with Notepad and similar tools. Passing `encoding`
    forces that codec with no fallback.
    """
    raw = path.read_bytes()

    if encoding is not None:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as exc:
            raise TextFileError(
                f"指定されたエンコーディング {encoding!r} でファイルを読み込めません: {path}"
            ) from exc

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp932")
        except UnicodeDecodeError as exc:
            raise TextFileError(
                f"UTF-8/CP932のいずれでもファイルを読み込めません: {path}"
            ) from exc


def display_width(text: str) -> int:
    """Terminal display width, counting East Asian wide/fullwidth chars as 2.

    `len()` is not usable for column alignment in this project because
    Japanese text is half the character count of its rendered width.
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad_to_width(text: str, width: int) -> str:
    """Left-align `text` padded with spaces to `width` display columns."""
    padding = width - display_width(text)
    return text + " " * max(0, padding)


def truncate_to_width(text: str, width: int, ellipsis: str = "...") -> str:
    """Truncate `text` so it fits within `width` display columns.

    When truncation happens, `ellipsis` is appended and counted toward the
    limit, so the result never exceeds `width`.
    """
    if display_width(text) <= width:
        return text

    ellipsis_width = display_width(ellipsis)
    budget = width - ellipsis_width
    if budget <= 0:
        return ellipsis[:width]

    result: list[str] = []
    used = 0
    for char in text:
        char_width = display_width(char)
        if used + char_width > budget:
            break
        result.append(char)
        used += char_width

    return "".join(result) + ellipsis
