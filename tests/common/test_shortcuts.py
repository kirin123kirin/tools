from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workpytools.common import shortcuts as shortcuts_module
from workpytools.common.shortcuts import (
    StartMenuLocationError,
    create_shortcuts,
    remove_shortcuts,
    scripts_dir,
    start_menu_dir,
)

# --- scripts_dir ---


def test_scripts_dir_venv_style_interpreter_in_scripts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # venv: python.exe自身がScripts/直下にあり、隣にtools.exeもある
    venv_scripts = tmp_path / "venv" / "Scripts"
    venv_scripts.mkdir(parents=True)
    (venv_scripts / "python.exe").write_bytes(b"")
    (venv_scripts / "tools.exe").write_bytes(b"")
    monkeypatch.setattr(shortcuts_module.sys, "executable", str(venv_scripts / "python.exe"))

    assert scripts_dir() == venv_scripts


def test_scripts_dir_base_install_style_interpreter_above_scripts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # pyenv-win等: python.exeがトップレベルにあり、Scripts/がその子
    base_dir = tmp_path / "3.12.10"
    scripts_subdir = base_dir / "Scripts"
    scripts_subdir.mkdir(parents=True)
    (base_dir / "python.exe").write_bytes(b"")
    (scripts_subdir / "tools.exe").write_bytes(b"")
    monkeypatch.setattr(shortcuts_module.sys, "executable", str(base_dir / "python.exe"))

    assert scripts_dir() == scripts_subdir


# --- start_menu_dir ---


def test_start_menu_dir_under_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", r"C:\fake\AppData\Roaming")
    expected = Path(
        r"C:\fake\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\workpytools"
    )
    assert start_menu_dir() == expected


def test_missing_appdata_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    with pytest.raises(StartMenuLocationError):
        start_menu_dir()


# --- create_shortcuts ---


@pytest.fixture
def fake_shell(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    shell = MagicMock()
    dispatch = MagicMock(return_value=shell)
    monkeypatch.setattr(shortcuts_module.win32com.client, "Dispatch", dispatch)
    return shell


def _make_exe(tmp_path: Path, name: str) -> Path:
    exe_dir = tmp_path / "Scripts"
    exe_dir.mkdir(exist_ok=True)
    exe_path = exe_dir / f"{name}.exe"
    exe_path.write_bytes(b"")
    return exe_path


def test_create_shortcuts_creates_one_lnk_per_existing_exe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_shell: MagicMock
) -> None:
    _make_exe(tmp_path, "touka")
    _make_exe(tmp_path, "denoise")
    monkeypatch.setattr(shortcuts_module, "scripts_dir", lambda: tmp_path / "Scripts")
    monkeypatch.setattr(shortcuts_module, "app_icon_path", lambda: tmp_path / "app.ico")

    target_dir = tmp_path / "StartMenu"
    created = create_shortcuts(["touka", "denoise"], target_dir=target_dir)

    assert len(created) == 2
    assert fake_shell.CreateShortCut.call_count == 2


def test_create_shortcuts_skips_missing_exe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_shell: MagicMock
) -> None:
    _make_exe(tmp_path, "touka")
    monkeypatch.setattr(shortcuts_module, "scripts_dir", lambda: tmp_path / "Scripts")
    monkeypatch.setattr(shortcuts_module, "app_icon_path", lambda: tmp_path / "app.ico")

    target_dir = tmp_path / "StartMenu"
    created = create_shortcuts(["touka", "does_not_exist"], target_dir=target_dir)

    assert len(created) == 1
    assert created[0].stem == "touka"


def test_create_shortcuts_sets_target_and_icon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_shell: MagicMock
) -> None:
    exe_path = _make_exe(tmp_path, "touka")
    icon_path = tmp_path / "app.ico"
    monkeypatch.setattr(shortcuts_module, "scripts_dir", lambda: tmp_path / "Scripts")
    monkeypatch.setattr(shortcuts_module, "app_icon_path", lambda: icon_path)

    shortcut_obj = fake_shell.CreateShortCut.return_value
    target_dir = tmp_path / "StartMenu"
    create_shortcuts(["touka"], target_dir=target_dir)

    assert shortcut_obj.TargetPath == str(exe_path)
    assert shortcut_obj.IconLocation == str(icon_path)
    shortcut_obj.Save.assert_called_once()


def test_create_shortcuts_creates_target_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_shell: MagicMock
) -> None:
    _make_exe(tmp_path, "touka")
    monkeypatch.setattr(shortcuts_module, "scripts_dir", lambda: tmp_path / "Scripts")
    monkeypatch.setattr(shortcuts_module, "app_icon_path", lambda: tmp_path / "app.ico")

    target_dir = tmp_path / "nested" / "StartMenu"
    create_shortcuts(["touka"], target_dir=target_dir)

    assert target_dir.is_dir()


# --- remove_shortcuts ---


def test_remove_shortcuts_deletes_lnk_files_and_folder(tmp_path: Path) -> None:
    target_dir = tmp_path / "StartMenu"
    target_dir.mkdir()
    (target_dir / "touka.lnk").write_bytes(b"")
    (target_dir / "denoise.lnk").write_bytes(b"")

    removed = remove_shortcuts(target_dir=target_dir)

    assert removed == 2
    assert not target_dir.exists()


def test_remove_shortcuts_missing_folder_is_noop(tmp_path: Path) -> None:
    target_dir = tmp_path / "does-not-exist"
    assert remove_shortcuts(target_dir=target_dir) == 0


def test_remove_shortcuts_keeps_folder_if_unrelated_files_remain(tmp_path: Path) -> None:
    target_dir = tmp_path / "StartMenu"
    target_dir.mkdir()
    (target_dir / "touka.lnk").write_bytes(b"")
    (target_dir / "readme.txt").write_bytes(b"")

    removed = remove_shortcuts(target_dir=target_dir)

    assert removed == 1
    assert target_dir.is_dir()
    assert (target_dir / "readme.txt").exists()
