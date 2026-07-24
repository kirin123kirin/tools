from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from tools.common.clipboard import LoadedImage, copy_file_to_clipboard, copy_image_to_clipboard


def save_result(
    loaded: LoadedImage, result: Image.Image, command: str, output: str | None
) -> Path | None:
    """Save `result` following the shared output convention for touka/denoise/kukiri.

    - `output` explicitly given: save there, no clipboard interaction.
    - input was an explicit path or a file copied in Explorer (`source_path`
      set): save next to the source file as `{stem}_{command}.png`.
    - input was raw clipboard image data (no source file): don't save to
      disk; put the processed image directly on the clipboard as data.

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
