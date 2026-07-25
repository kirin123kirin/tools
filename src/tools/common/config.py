from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a TOML config file into a dict."""
    with Path(path).open("rb") as f:
        return tomllib.load(f)


def default_config_path() -> Path:
    """Default location of the shared tools config file: %APPDATA%\\tools\\config.toml."""
    return Path(os.environ["APPDATA"]) / "tools" / "config.toml"


def load_default_config() -> dict[str, Any]:
    """Load the default config file, or return {} if it doesn't exist."""
    path = default_config_path()
    if not path.exists():
        return {}
    return load_config(path)
