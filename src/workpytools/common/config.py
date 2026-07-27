from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a TOML config file into a dict."""
    with Path(path).open("rb") as f:
        return tomllib.load(f)


class ConfigLocationError(RuntimeError):
    """Raised when the per-user config location can't be determined."""


def _appdata_dir() -> Path:
    """%APPDATA%\\workpytools, with a clear error instead of a bare KeyError."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise ConfigLocationError(
            "環境変数 APPDATA が設定されていないため、設定の保存先を決定できません"
        )
    return Path(appdata) / "workpytools"


def default_config_path() -> Path:
    """Default location of the shared config file: %APPDATA%\\workpytools\\config.toml."""
    return _appdata_dir() / "config.toml"


def vv_prompts_dir() -> Path:
    """Folder holding one .txt per saved prompt: %APPDATA%\\workpytools\\vv\\."""
    return _appdata_dir() / "vv"


def load_default_config() -> dict[str, Any]:
    """Load the default config file, or return {} if it doesn't exist."""
    path = default_config_path()
    if not path.exists():
        return {}
    return load_config(path)
