from pathlib import Path

import pytest
from PIL import Image

from tools.cli import _discover_processors, build_parser, run_as_subcommand
from tools.processing import denoise as denoise_module


def _fake_fast_nl_means_denoising_colored(
    src, dst, h, hColor, templateWindowSize, searchWindowSize
):
    return src


def test_discover_processors_finds_registered_commands() -> None:
    processors = _discover_processors()
    assert "denoise" in processors
    assert "touka" in processors
    assert "kukiri" in processors


def test_build_parser_registers_subcommand() -> None:
    processors = _discover_processors()
    parser = build_parser(processors)
    args = parser.parse_args(["denoise", "photo.jpg"])
    assert args.command == "denoise"
    assert args.path == "photo.jpg"


def test_run_as_subcommand_uses_program_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "out.png"
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )
    monkeypatch.setattr("sys.argv", ["/usr/local/bin/denoise", str(src), "-o", str(out)])

    result = run_as_subcommand()

    assert result == 0
    assert out.exists()


def test_run_as_subcommand_strips_exe_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), color="white").save(src)
    out = tmp_path / "out.png"
    monkeypatch.setattr(
        denoise_module.cv2,
        "fastNlMeansDenoisingColored",
        _fake_fast_nl_means_denoising_colored,
    )
    monkeypatch.setattr("sys.argv", [r"C:\tools\Scripts\denoise.exe", str(src), "-o", str(out)])

    result = run_as_subcommand()

    assert result == 0
    assert out.exists()
