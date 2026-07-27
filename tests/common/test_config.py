from pathlib import Path

import pytest

from workpytools.common.config import (
    ConfigLocationError,
    default_config_path,
    load_default_config,
    vv_prompts_dir,
)


def test_default_config_path_under_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", r"C:\fake\AppData\Roaming")
    assert default_config_path() == Path(r"C:\fake\AppData\Roaming\workpytools\config.toml")


def test_vv_prompts_dir_under_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", r"C:\fake\AppData\Roaming")
    assert vv_prompts_dir() == Path(r"C:\fake\AppData\Roaming\workpytools\vv")


def test_missing_appdata_raises_config_location_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPDATA", raising=False)

    with pytest.raises(ConfigLocationError):
        vv_prompts_dir()

    with pytest.raises(ConfigLocationError):
        default_config_path()


def test_empty_appdata_also_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", "")

    with pytest.raises(ConfigLocationError):
        vv_prompts_dir()


def test_load_default_config_returns_empty_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_default_config() == {}


def test_load_default_config_reads_toml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config_dir = tmp_path / "workpytools"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('[cwc]\nuser_dict = "x.csv"\n', encoding="utf-8")

    config = load_default_config()
    assert config["cwc"]["user_dict"] == "x.csv"
