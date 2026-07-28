from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

import win32com.client


class StartMenuLocationError(RuntimeError):
    """Raised when the per-user Start Menu location can't be determined."""


_START_MENU_FOLDER_NAME = "workpytools"


def start_menu_dir() -> Path:
    """The per-user Start Menu folder holding our shortcuts:
    %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\workpytools\\."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise StartMenuLocationError(
            "環境変数 APPDATA が設定されていないため、スタートメニューの場所を決定できません"
        )
    programs_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return programs_dir / _START_MENU_FOLDER_NAME


def app_icon_path() -> Path:
    """Path to the bundled .ico used for every shortcut."""
    return Path(str(resources.files("workpytools.data") / "app.ico"))


def scripts_dir() -> Path:
    """Directory holding the per-command .exe launchers (e.g. `touka.exe`).

    In a venv, `python.exe` itself lives in `Scripts/`, so its own parent
    is the answer. In a base install (e.g. pyenv-win), `python.exe` lives
    one level above `Scripts/`, so it has to be appended. Prefer whichever
    of the two actually contains `tools.exe`, our own console_script.

    Not accounted for: `pip install --user`, which places scripts under
    `%APPDATA%\\Python\\PythonXY\\Scripts` rather than next to the
    interpreter. README only documents the venv setup, so this is out of
    scope for now.
    """
    interpreter_dir = Path(sys.executable).parent
    if (interpreter_dir / "tools.exe").exists():
        return interpreter_dir
    return interpreter_dir / "Scripts"


def create_shortcuts(commands: list[str], target_dir: Path | None = None) -> list[Path]:
    """Create one .lnk per command name under the Start Menu folder,
    pointing at `<scripts_dir>/<command>.exe`. Returns the created paths.

    Commands whose .exe isn't found in `scripts_dir()` are skipped rather
    than raising, so a partial install doesn't block the rest.
    """
    menu_dir = target_dir if target_dir is not None else start_menu_dir()
    menu_dir.mkdir(parents=True, exist_ok=True)

    shell = win32com.client.Dispatch("WScript.Shell")
    icon = app_icon_path()
    exe_dir = scripts_dir()

    created: list[Path] = []
    for command in commands:
        exe_path = exe_dir / f"{command}.exe"
        if not exe_path.exists():
            continue

        link_path = menu_dir / f"{command}.lnk"
        shortcut = shell.CreateShortCut(str(link_path))
        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_dir)
        shortcut.IconLocation = str(icon)
        shortcut.Save()
        created.append(link_path)

    return created


def remove_shortcuts(target_dir: Path | None = None) -> int:
    """Delete the Start Menu folder and every shortcut in it. Returns the
    number of .lnk files removed. No-op (returns 0) if the folder doesn't
    exist."""
    menu_dir = target_dir if target_dir is not None else start_menu_dir()
    if not menu_dir.is_dir():
        return 0

    removed = 0
    for entry in menu_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".lnk":
            entry.unlink()
            removed += 1

    try:
        menu_dir.rmdir()
    except OSError:
        pass  # 想定外のファイルが残っていれば、フォルダごとの削除はスキップする

    return removed
