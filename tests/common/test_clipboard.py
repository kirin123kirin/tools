from pathlib import Path

import pytest
from PIL import Image

from tools.common.clipboard import (
    ClipboardImageError,
    copy_file_to_clipboard,
    copy_image_to_clipboard,
    load_image,
)


def test_load_image_from_path(tmp_path: Path) -> None:
    img_path = tmp_path / "sample.png"
    Image.new("RGB", (2, 2), color="red").save(img_path)

    result = load_image(str(img_path))

    assert result.image.mode == "RGBA"
    assert result.image.size == (2, 2)
    assert result.source_path == img_path
    assert result.source_kind == "path"


def test_load_image_from_clipboard_image_data(monkeypatch: pytest.MonkeyPatch) -> None:
    clip_image = Image.new("RGB", (3, 3), color="blue")
    monkeypatch.setattr("tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image)

    result = load_image(None)

    assert result.image.mode == "RGBA"
    assert result.image.size == (3, 3)
    assert result.source_path is None
    assert result.source_kind == "clipboard_data"


def test_load_image_from_clipboard_file_object(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    img_path = tmp_path / "copied.png"
    Image.new("RGB", (4, 4), color="green").save(img_path)
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: [str(img_path)]
    )

    result = load_image(None)

    assert result.image.size == (4, 4)
    assert result.source_path == img_path
    assert result.source_kind == "clipboard_file"


def test_load_image_from_empty_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tools.common.clipboard.ImageGrab.grabclipboard", lambda: None)

    with pytest.raises(ClipboardImageError):
        load_image(None)


def test_copy_file_to_clipboard_sets_cf_hdrop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[int, bytes]] = []
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.OpenClipboard", lambda: None)
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.EmptyClipboard", lambda: None)
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.CloseClipboard", lambda: None)
    monkeypatch.setattr(
        "tools.common.clipboard.win32clipboard.SetClipboardData",
        lambda fmt, data: calls.append((fmt, data)),
    )

    file_path = tmp_path / "out.png"
    file_path.write_bytes(b"dummy")
    copy_file_to_clipboard(file_path)

    assert len(calls) == 1
    fmt, data = calls[0]
    import win32con

    assert fmt == win32con.CF_HDROP
    assert str(file_path.resolve()).encode("utf-16-le") in data


def test_copy_image_to_clipboard_sets_cf_dib(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, bytes]] = []
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.OpenClipboard", lambda: None)
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.EmptyClipboard", lambda: None)
    monkeypatch.setattr("tools.common.clipboard.win32clipboard.CloseClipboard", lambda: None)
    monkeypatch.setattr(
        "tools.common.clipboard.win32clipboard.SetClipboardData",
        lambda fmt, data: calls.append((fmt, data)),
    )

    image = Image.new("RGB", (2, 2), color="red")
    copy_image_to_clipboard(image)

    assert len(calls) == 1
    fmt, data = calls[0]
    import win32con

    assert fmt == win32con.CF_DIB
    assert len(data) > 0
