import argparse
from pathlib import Path

import pytest
from PIL import Image

from workpytools.processing import touka as touka_module
from workpytools.processing.touka import ToukaProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = dict(
        path=None,
        output=None,
        alpha_matting=False,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
        bgcolor=None,
        only_mask=False,
        post_process_mask=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_run_saves_output_next_to_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (5, 5), color="white").save(src)
    monkeypatch.setattr(touka_module, "remove", lambda img, **kwargs: img)

    proc = ToukaProcessor()
    args = _base_args(path=str(src))
    result = proc.run(args)

    expected = tmp_path / "photo_touka.png"
    assert result == 0
    assert expected.exists()


def test_run_with_explicit_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "custom.png"
    monkeypatch.setattr(touka_module, "remove", lambda img, **kwargs: img)

    proc = ToukaProcessor()
    args = _base_args(path=str(src), output=str(out))
    proc.run(args)

    assert out.exists()


def test_run_from_clipboard_image_copies_data_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clip_image = Image.new("RGB", (5, 5), color="white")
    monkeypatch.setattr(
        "workpytools.common.clipboard.ImageGrab.grabclipboard", lambda: clip_image
    )
    monkeypatch.setattr(touka_module, "remove", lambda img, **kwargs: img)
    monkeypatch.chdir(tmp_path)
    copied = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_image_to_clipboard", lambda img: copied.append(img)
    )

    proc = ToukaProcessor()
    args = _base_args()
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
    monkeypatch.setattr(touka_module, "remove", lambda img, **kwargs: img)
    monkeypatch.setattr("workpytools.common.output.tempfile.gettempdir", lambda: str(tmpdir))
    clipboard_calls = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_file_to_clipboard", lambda p: clipboard_calls.append(p)
    )

    proc = ToukaProcessor()
    args = _base_args()
    proc.run(args)

    expected = tmpdir / "copied_touka.png"
    assert expected.exists()
    assert clipboard_calls == [expected]


def test_run_passes_alpha_matting_options_to_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        touka_module, "remove", lambda img, **kwargs: (calls.append(kwargs), img)[1]
    )

    proc = ToukaProcessor()
    args = _base_args(
        path=str(src),
        alpha_matting=True,
        alpha_matting_foreground_threshold=250,
        alpha_matting_background_threshold=5,
        alpha_matting_erode_size=15,
    )
    proc.run(args)

    assert calls[0]["alpha_matting"] is True
    assert calls[0]["alpha_matting_foreground_threshold"] == 250
    assert calls[0]["alpha_matting_background_threshold"] == 5
    assert calls[0]["alpha_matting_erode_size"] == 15


def test_run_passes_bgcolor_as_tuple_to_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        touka_module, "remove", lambda img, **kwargs: (calls.append(kwargs), img)[1]
    )

    proc = ToukaProcessor()
    args = _base_args(path=str(src), bgcolor=[255, 255, 255, 255])
    proc.run(args)

    assert calls[0]["bgcolor"] == (255, 255, 255, 255)


def test_run_bgcolor_omitted_passes_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        touka_module, "remove", lambda img, **kwargs: (calls.append(kwargs), img)[1]
    )

    proc = ToukaProcessor()
    args = _base_args(path=str(src))
    proc.run(args)

    assert calls[0]["bgcolor"] is None


def test_run_passes_only_mask_and_post_process_mask_to_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        touka_module, "remove", lambda img, **kwargs: (calls.append(kwargs), img)[1]
    )

    proc = ToukaProcessor()
    args = _base_args(path=str(src), only_mask=True, post_process_mask=True)
    proc.run(args)

    assert calls[0]["only_mask"] is True
    assert calls[0]["post_process_mask"] is True
