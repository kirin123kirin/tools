import argparse
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.processing import denoise as denoise_module
from tools.processing.denoise import DenoiseProcessor


def _fake_fast_nl_means_denoising_colored(
    src, dst, h, hColor, templateWindowSize, searchWindowSize
):
    return src


def test_run_saves_output_next_to_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (5, 5), color="white").save(src)
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )

    proc = DenoiseProcessor()
    args = argparse.Namespace(path=str(src), output=None, strength=10.0)
    result = proc.run(args)

    expected = tmp_path / "photo_denoised.png"
    assert result == 0
    assert expected.exists()


def test_run_with_explicit_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "custom.png"
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )

    proc = DenoiseProcessor()
    args = argparse.Namespace(path=str(src), output=str(out), strength=10.0)
    proc.run(args)

    assert out.exists()


def test_run_from_clipboard_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "tools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )
    monkeypatch.chdir(tmp_path)

    proc = DenoiseProcessor()
    args = argparse.Namespace(path=None, output=None, strength=10.0)
    proc.run(args)

    assert list(tmp_path.glob("clipboard_denoised_*.png"))


def test_denoise_preserves_alpha_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[:, :, 3] = 128
    image = Image.fromarray(rgba, mode="RGBA")

    result = DenoiseProcessor._denoise(image, h=10.0)

    assert np.array_equal(np.array(result)[:, :, 3], rgba[:, :, 3])
