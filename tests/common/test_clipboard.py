from pathlib import Path

import pytest
from PIL import Image

from workpytools.common.clipboard import (
    ClipboardImageError,
    ClipboardTextError,
    copy_file_to_clipboard,
    copy_image_to_clipboard,
    load_image,
    load_text,
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
    monkeypatch.setattr("workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image)

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
        "workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: [str(img_path)]
    )

    result = load_image(None)

    assert result.image.size == (4, 4)
    assert result.source_path == img_path
    assert result.source_kind == "clipboard_file"


def test_load_image_from_empty_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: None)

    with pytest.raises(ClipboardImageError):
        load_image(None)


def test_copy_file_to_clipboard_sets_cf_hdrop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[int, bytes]] = []
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None)
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.EmptyClipboard", lambda: None)
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None)
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.SetClipboardData",
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


def _dispatch_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, bytes]]:
    calls: list[tuple[int, bytes]] = []
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None)
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.EmptyClipboard", lambda: None)
    monkeypatch.setattr("workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None)
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.RegisterClipboardFormat",
        lambda name: 49356,  # "PNG"の実際の登録値を模した適当な固定ID
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.SetClipboardData",
        lambda fmt, data: calls.append((fmt, data)),
    )
    return calls


def test_copy_image_to_clipboard_sets_png_dibv5_and_dib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PowerPoint/Word/ブラウザはCF_DIBV5単体だと貼り付けを認識しないことがある
    # ため、優先度の高い"PNG"カスタムフォーマットを筆頭に、CF_DIBV5・CF_DIBの
    # 3形式を同時に提供する
    calls = _dispatch_calls(monkeypatch)

    image = Image.new("RGB", (2, 2), color="red")
    copy_image_to_clipboard(image)

    import win32con

    formats = [fmt for fmt, _ in calls]
    assert formats == [49356, win32con.CF_DIBV5, win32con.CF_DIB]
    assert all(len(data) > 0 for _, data in calls)


def test_copy_image_to_clipboard_png_bytes_are_valid_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _dispatch_calls(monkeypatch)

    image = Image.new("RGBA", (3, 3), color=(1, 2, 3, 4))
    copy_image_to_clipboard(image)

    png_bytes = calls[0][1]
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_copy_image_to_clipboard_dibv5_preserves_alpha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # touka等が返す透過画像が、CF_DIBV5のアルファマスク経由で黒塗りされずに
    # 残ること（アルファなしRGB変換だと透過部分が黒くなる不具合の回帰防止）
    calls = _dispatch_calls(monkeypatch)

    image = Image.new("RGBA", (1, 1), color=(255, 0, 0, 0))  # 完全透明の赤ピクセル
    copy_image_to_clipboard(image)

    dibv5_data = calls[1][1]
    header_size = 124
    pixel = dibv5_data[header_size : header_size + 4]  # BGRAの1ピクセル
    assert pixel == bytes([0, 0, 255, 0])  # B=0, G=0, R=255, A=0（アルファが保持されている）


def test_copy_image_to_clipboard_dib_flattens_alpha_onto_white(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # CF_DIBはアルファ非対応のため、透過部分は白背景に合成してフォールバック
    # させる（黒塗りにはしない）
    calls = _dispatch_calls(monkeypatch)

    image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 0))  # 完全透明の黒ピクセル
    copy_image_to_clipboard(image)

    dib_data = calls[2][1]
    header_size = 40
    pixel = dib_data[header_size : header_size + 3]  # BGRの1ピクセル
    assert pixel == bytes([255, 255, 255])  # 白背景に合成されている


def test_load_text_from_path_utf8(tmp_path: Path) -> None:
    path = tmp_path / "memo.txt"
    path.write_bytes("こんにちは\r\n世界\r".encode())

    result = load_text(str(path))

    assert result.source_path == path
    assert result.source_kind == "path"
    assert result.text == "こんにちは\n世界\n"


def test_load_text_from_path_utf8_sig(tmp_path: Path) -> None:
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "こんにちは".encode())

    result = load_text(str(path))

    assert result.text == "こんにちは"


def test_load_text_from_path_cp932_fallback(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("こんにちは".encode("cp932"))

    result = load_text(str(path))

    assert result.text == "こんにちは"


def test_load_text_with_explicit_encoding(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("こんにちは".encode("cp932"))

    result = load_text(str(path), encoding="cp932")

    assert result.text == "こんにちは"


def test_load_text_with_wrong_explicit_encoding_raises(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("こんにちは".encode("cp932"))

    with pytest.raises(ClipboardTextError):
        load_text(str(path), encoding="utf-8")


def test_load_text_from_clipboard_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None
    )

    def fake_is_available(fmt: int) -> bool:
        import win32clipboard as wc

        return fmt == wc.CF_UNICODETEXT

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.IsClipboardFormatAvailable",
        fake_is_available,
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.GetClipboardData",
        lambda fmt: "クリップボードのテキスト\r\n続き",
    )

    result = load_text(None)

    assert result.source_path is None
    assert result.source_kind == "clipboard_text"
    assert result.text == "クリップボードのテキスト\n続き"


def test_load_text_from_clipboard_file_object(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "copied.txt"
    path.write_text("コピーされたファイル", encoding="utf-8")

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None
    )

    def fake_is_available(fmt: int) -> bool:
        import win32clipboard as wc

        return fmt == wc.CF_HDROP

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.IsClipboardFormatAvailable",
        fake_is_available,
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.GetClipboardData",
        lambda fmt: [str(path)],
    )

    result = load_text(None)

    assert result.source_path == path
    assert result.source_kind == "clipboard_file"
    assert result.text == "コピーされたファイル"


def test_load_text_from_empty_clipboard_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.IsClipboardFormatAvailable",
        lambda fmt: False,
    )

    with pytest.raises(ClipboardTextError):
        load_text(None)
