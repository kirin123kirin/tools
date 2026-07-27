import argparse
from pathlib import Path

import pytest

from workpytools.processing import help as help_module
from workpytools.processing.help import HelpProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(no_open=True)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_missing_help_html_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(help_module, "_HELP_HTML_PATH", tmp_path / "does_not_exist.html")
    proc = HelpProcessor()
    with pytest.raises(SystemExit):
        proc.run(_base_args())


def test_existing_help_html_prints_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    html_path = tmp_path / "help.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(help_module, "_HELP_HTML_PATH", html_path)

    proc = HelpProcessor()
    proc.run(_base_args(no_open=True))

    captured = capsys.readouterr()
    assert str(html_path) in captured.out


def test_no_open_skips_browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    html_path = tmp_path / "help.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(help_module, "_HELP_HTML_PATH", html_path)

    calls = []
    monkeypatch.setattr(help_module.webbrowser, "open", lambda url: calls.append(url))

    proc = HelpProcessor()
    proc.run(_base_args(no_open=True))

    assert calls == []


def test_opens_browser_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    html_path = tmp_path / "help.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(help_module, "_HELP_HTML_PATH", html_path)

    calls = []
    monkeypatch.setattr(help_module.webbrowser, "open", lambda url: calls.append(url))

    proc = HelpProcessor()
    proc.run(_base_args(no_open=False))

    assert len(calls) == 1
