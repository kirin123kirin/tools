import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workpytools.common.shortcuts import StartMenuLocationError
from workpytools.processing import shortcut as shortcut_module
from workpytools.processing.shortcut import ShortcutProcessor


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = dict(remove=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_run_creates_shortcuts_for_all_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(shortcut_module, "start_menu_dir", lambda: tmp_path)
    create = MagicMock(return_value=[tmp_path / "touka.lnk", tmp_path / "denoise.lnk"])
    monkeypatch.setattr(shortcut_module, "create_shortcuts", create)
    monkeypatch.setattr(
        shortcut_module, "_all_standalone_names", lambda: ["touka", "denoise"]
    )

    result = ShortcutProcessor().run(_base_args())

    assert result == 0
    create.assert_called_once_with(["touka", "denoise"])


def test_run_reports_skipped_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(shortcut_module, "start_menu_dir", lambda: tmp_path)
    monkeypatch.setattr(
        shortcut_module, "create_shortcuts", lambda commands: [tmp_path / "touka.lnk"]
    )
    monkeypatch.setattr(
        shortcut_module, "_all_standalone_names", lambda: ["touka", "does_not_exist"]
    )

    ShortcutProcessor().run(_base_args())

    out = capsys.readouterr().out
    assert "1個は対応するexeが見つからずスキップ" in out


def test_run_with_remove_calls_remove_shortcuts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(shortcut_module, "start_menu_dir", lambda: tmp_path)
    remove = MagicMock(return_value=3)
    monkeypatch.setattr(shortcut_module, "remove_shortcuts", remove)
    create = MagicMock()
    monkeypatch.setattr(shortcut_module, "create_shortcuts", create)

    result = ShortcutProcessor().run(_base_args(remove=True))

    assert result == 0
    remove.assert_called_once()
    create.assert_not_called()


def test_run_remove_reports_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(shortcut_module, "start_menu_dir", lambda: tmp_path)
    monkeypatch.setattr(shortcut_module, "remove_shortcuts", lambda: 5)

    ShortcutProcessor().run(_base_args(remove=True))

    out = capsys.readouterr().out
    assert "5個のショートカットを削除しました" in out


def test_missing_appdata_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error() -> Path:
        raise StartMenuLocationError("no APPDATA")

    monkeypatch.setattr(shortcut_module, "start_menu_dir", raise_error)

    with pytest.raises(SystemExit):
        ShortcutProcessor().run(_base_args())
