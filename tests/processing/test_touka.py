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


def test_run_from_clipboard_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(touka_module, "remove", lambda img: img)
    monkeypatch.chdir(tmp_path)

    proc = ToukaProcessor()
    args = argparse.Namespace(path=None, output=None)
    proc.run(args)

    assert list(tmp_path.glob("clipboard_touka_*.png"))
