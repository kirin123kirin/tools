from pathlib import Path

import pytest
from PIL import Image

from tools.common.clipboard import LoadedImage
from tools.common.output import save_result


def _image() -> Image.Image:
    return Image.new("RGBA", (2, 2), color="red")


def test_explicit_output_overrides_everything(tmp_path: Path) -> None:
    loaded = LoadedImage(image=_image(), source_path=None, source_kind="clipboard_data")
    explicit = tmp_path / "explicit.png"

    result_path = save_result(loaded, _image(), "touka", str(explicit))

    assert result_path == explicit
    assert explicit.exists()


def test_path_input_saves_next_to_source(tmp_path: Path) -> None:
    source = tmp_path / "foo.png"
    source.write_bytes(b"dummy")
    loaded = LoadedImage(image=_image(), source_path=source, source_kind="path")

    result_path = save_result(loaded, _image(), "touka", None)

    assert result_path == tmp_path / "foo_touka.png"
    assert result_path.exists()


def test_clipboard_file_input_saves_to_tmpdir_and_copies_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "bar.png"
    source.write_bytes(b"dummy")
    loaded = LoadedImage(image=_image(), source_path=source, source_kind="clipboard_file")

    calls: list[Path] = []
    monkeypatch.setattr(
        "tools.common.output.copy_file_to_clipboard", lambda p: calls.append(p)
    )
    monkeypatch.setattr("tools.common.output.tempfile.gettempdir", lambda: str(tmp_path))

    result_path = save_result(loaded, _image(), "touka", None)

    assert result_path == tmp_path / "bar_touka.png"
    assert result_path.exists()
    assert calls == [result_path]


def test_clipboard_data_input_writes_no_file_and_copies_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = LoadedImage(image=_image(), source_path=None, source_kind="clipboard_data")

    calls: list[Image.Image] = []
    monkeypatch.setattr(
        "tools.common.output.copy_image_to_clipboard", lambda img: calls.append(img)
    )

    result_path = save_result(loaded, _image(), "touka", None)

    assert result_path is None
    assert len(calls) == 1
