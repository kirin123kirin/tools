import pytest

from tools.cli import _discover_processors, build_parser, run_as_subcommand


def test_discover_processors_finds_example() -> None:
    processors = _discover_processors()
    assert "example" in processors


def test_build_parser_registers_subcommand() -> None:
    processors = _discover_processors()
    parser = build_parser(processors)
    args = parser.parse_args(["example", "hi"])
    assert args.command == "example"
    assert args.text == "hi"


def test_run_as_subcommand_uses_program_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["/usr/local/bin/example", "hi"])

    result = run_as_subcommand()

    assert result == 0
    assert capsys.readouterr().out.strip() == "HI"


def test_run_as_subcommand_strips_exe_suffix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", [r"C:\tools\Scripts\example.exe", "hi"])

    result = run_as_subcommand()

    assert result == 0
    assert capsys.readouterr().out.strip() == "HI"
