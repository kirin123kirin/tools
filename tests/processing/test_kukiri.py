import argparse
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.processing import kukiri as kukiri_module
from tools.processing.kukiri import KukiriProcessor


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


def test_run_from_clipboard_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(kukiri_module.cv2, "bilateralFilter", _identity_filter)
    monkeypatch.setattr(kukiri_module.cv2, "GaussianBlur", _identity_filter)
    monkeypatch.chdir(tmp_path)

    proc = KukiriProcessor()
    args = argparse.Namespace(path=None, output=None, smooth=75.0, sharpen=0.5)
    proc.run(args)

    assert list(tmp_path.glob("clipboard_kukiri_*.png"))


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
