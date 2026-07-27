import argparse
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workpytools.processing import kukiri as kukiri_module
from workpytools.processing.kukiri import KukiriProcessor


def _identity_filter(*args, **kwargs):
    return args[0]


def test_run_saves_output_next_to_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (5, 5), color="white").save(src)
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)

    proc = KukiriProcessor()
    args = argparse.Namespace(path=str(src), output=None, smooth=75.0, sharpen=0.5)
    result = proc.run(args)

    expected = tmp_path / "photo_kukiri.png"
    assert result == 0
    assert expected.exists()


def test_run_with_explicit_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "custom.png"
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)

    proc = KukiriProcessor()
    args = argparse.Namespace(path=str(src), output=str(out), smooth=75.0, sharpen=0.5)
    proc.run(args)

    assert out.exists()


def test_run_from_clipboard_image_copies_data_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)
    monkeypatch.chdir(tmp_path)
    copied = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_image_to_clipboard", lambda img: copied.append(img)
    )

    proc = KukiriProcessor()
    args = argparse.Namespace(path=None, output=None, smooth=75.0, sharpen=0.5)
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
        "workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: [str(copied_src)]
    )
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)
    monkeypatch.setattr("workpytools.common.output.tempfile.gettempdir", lambda: str(tmpdir))
    clipboard_calls = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_file_to_clipboard", lambda p: clipboard_calls.append(p)
    )

    proc = KukiriProcessor()
    args = argparse.Namespace(path=None, output=None, smooth=75.0, sharpen=0.5)
    proc.run(args)

    expected = tmpdir / "copied_kukiri.png"
    assert expected.exists()
    assert clipboard_calls == [expected]


def test_process_preserves_alpha_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[:, :, 3] = 128
    image = Image.fromarray(rgba, mode="RGBA")

    result = KukiriProcessor._process(image, smooth=75.0, sharpen=0.5)

    assert np.array_equal(np.array(result)[:, :, 3], rgba[:, :, 3])


def test_process_with_zero_sharpen_is_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)
    rgba = np.full((4, 4, 4), 100, dtype=np.uint8)
    image = Image.fromarray(rgba, mode="RGBA")

    result = KukiriProcessor._process(image, smooth=75.0, sharpen=0.0)

    assert np.array_equal(np.array(result), rgba)
