from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a TOML config file into a dict."""
    with Path(path).open("rb") as f:
        return tomllib.load(f)
