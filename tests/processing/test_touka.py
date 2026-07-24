import argparse
from pathlib import Path

import pytest
from PIL import Image

from tools.processing import touka as touka_module
from tools.processing.touka import ToukaProcessor


def test_run_saves_output_next_to_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (5, 5), color="white").save(src)
    monkeypatch.setattr(touka_module, "remove", lambda img: img)

    proc = ToukaProcessor()
    args = argparse.Namespace(path=str(src), output=None)
    result = proc.run(args)

    expected = tmp_path / "photo_touka.png"
    assert result == 0
    assert expected.exists()


def test_run_with_explicit_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "custom.png"
    monkeypatch.setattr(touka_module, "remove", lambda img: img)

    proc = ToukaProcessor()
    args = argparse.Namespace(path=str(src), output=str(out))
    proc.run(args)

    assert out.exists()


def test_run_from_clipboard_image_copies_data_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(touka_module, "remove", lambda img: img)
    monkeypatch.chdir(tmp_path)
    copied = []
    monkeypatch.setattr(
        "tools.common.output.copy_image_to_clipboard", lambda img: copied.append(img)
    )

    proc = ToukaProcessor()
    args = argparse.Namespace(path=None, output=None)
    proc.run(args)

    assert not list(tmp_path.glob("*.png"))
    assert len(copied) == 1


def test_run_from_clipboard_file_object_saves_to_tmpdir_and_copies_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    copied_src = tmp_path / "copied.png"
    Image.new("RGB", (5, 5), color="white").save(copied_src)
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: [str(copied_src)]
    )
    monkeypatch.setattr(touka_module, "remove", lambda img: img)
    monkeypatch.setattr("tools.common.output.tempfile.gettempdir", lambda: str(tmpdir))
    clipboard_calls = []
    monkeypatch.setattr(
        "tools.common.output.copy_file_to_clipboard", lambda p: clipboard_calls.append(p)
    )

    proc = ToukaProcessor()
    args = argparse.Namespace(path=None, output=None)
    proc.run(args)

    expected = tmpdir / "copied_touka.png"
    assert expected.exists()
    assert clipboard_calls == [expected]
