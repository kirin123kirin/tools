from pathlib import Path

import pytest
from PIL import Image

from tools.common.clipboard import ClipboardImageError, load_image


def test_load_image_from_path(tmp_path: Path) -> None:
    img_path = tmp_path / "sample.png"
    Image.new("RGB", (2, 2), color="red").save(img_path)

    result = load_image(str(img_path))

    assert result.mode == "RGBA"
    assert result.size == (2, 2)


def test_load_image_from_clipboard_image_data(monkeypatch: pytest.MonkeyPatch) -> None:
    clip_image = Image.new("RGB", (3, 3), color="blue")
    monkeypatch.setattr("tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image)

    result = load_image(None)

    assert result.mode == "RGBA"
    assert result.size == (3, 3)


def test_load_image_from_clipboard_file_object(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    img_path = tmp_path / "copied.png"
    Image.new("RGB", (4, 4), color="green").save(img_path)
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: [str(img_path)]
    )

    result = load_image(None)

    assert result.size == (4, 4)


def test_load_image_from_empty_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tools.common.clipboard.ImageGrab.grabclipboard", lambda: None)

    with pytest.raises(ClipboardImageError):
        load_image(None)
