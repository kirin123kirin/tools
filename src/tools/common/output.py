from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol

from PIL import Image

from tools.common.clipboard import SourceKind, copy_file_to_clipboard, copy_image_to_clipboard


class HasSource(Protocol):
    """Structural type for anything that knows where its input data came from.

    `LoadedImage` and `LoadedText` both satisfy this. Attributes are declared
    as read-only properties because Protocol treats mutable attributes as
    invariant — a plain `source_kind: SourceKind` field would fail mypy
    strict unless the implementing class declares the exact same type.
    """

    @property
    def source_path(self) -> Path | None: ...
    @property
    def source_kind(self) -> SourceKind: ...


def save_result(
    loaded: HasSource, result: Image.Image, command: str, output: str | None
) -> Path | None:
    """Save `result` following the shared output convention across all commands.

    - `output` explicitly given: save there, no clipboard interaction.
    - `source_kind == "path"`: save next to the source file as
      `{stem}_{command}.png`.
    - `source_kind == "clipboard_file"` (a file copied in Explorer): save
      under the OS temp dir as `{stem}_{command}.png` and put that file on
      the clipboard, ready to paste.
    - otherwise (`clipboard_data` / `clipboard_text`, no source file): don't
      save to disk; put the processed image directly on the clipboard as data.

    Returns the path written to disk, or `None` when the result was only
    placed on the clipboard as raw image data.
    """
    if output is not None:
        output_path = Path(output)
        result.save(output_path)
        return output_path

    if loaded.source_kind == "path":
        assert loaded.source_path is not None
        output_path = loaded.source_path.with_name(f"{loaded.source_path.stem}_{command}.png")
        result.save(output_path)
        return output_path

    if loaded.source_kind == "clipboard_file":
        assert loaded.source_path is not None
        tmpdir = Path(tempfile.gettempdir())
        output_path = tmpdir / f"{loaded.source_path.stem}_{command}.png"
        result.save(output_path)
        copy_file_to_clipboard(output_path)
        return output_path

    copy_image_to_clipboard(result)
    return None


def describe_output(output_path: Path | None) -> str:
    """Human-readable line for `print()` after `save_result`."""
    if output_path is not None:
        return str(output_path)
    return "(クリップボードに画像データをコピーしました)"
