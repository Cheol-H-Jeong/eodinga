from __future__ import annotations

from pathlib import Path

from eodinga.config import AppConfig, RootConfig, default_path, load


def test_load_missing_file_returns_defaults(temp_config_path: Path) -> None:
    config = load(temp_config_path)
    assert isinstance(config, AppConfig)
    assert config.launcher.hotkey == "ctrl+shift+space"


def test_config_round_trip_save_and_load(temp_config_path: Path, tmp_path: Path) -> None:
    config = AppConfig(roots=[RootConfig(path=tmp_path / "docs")])
    config.save(temp_config_path)
    loaded = load(temp_config_path)
    assert loaded.model_dump() == config.model_dump()


def test_default_path_ends_with_config_toml() -> None:
    assert default_path().name == "config.toml"

