from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.config import AppConfig, RootConfig, default_path, load


def test_load_missing_file_returns_defaults(temp_config_path: Path) -> None:
    config = load(temp_config_path)
    assert isinstance(config, AppConfig)
    assert config.launcher.hotkey == "ctrl+shift+space"


def test_config_round_trip_save_and_load(temp_config_path: Path, tmp_path: Path) -> None:
    config = AppConfig(
        launcher=AppConfig().launcher.model_copy(
            update={
                "always_on_top": True,
                "window_x": 120,
                "window_y": 64,
                "window_width": 800,
                "window_height": 520,
            }
        ),
        roots=[RootConfig(path=tmp_path / "docs")],
    )
    config.save(temp_config_path)
    loaded = load(temp_config_path)
    assert loaded.model_dump() == config.model_dump()


def test_load_accepts_always_on_top_launcher_setting(
    temp_config_path: Path,
) -> None:
    temp_config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_config_path.write_text(
        """
[launcher]
always_on_top = true
""".strip(),
        encoding="utf-8",
    )

    loaded = load(temp_config_path)

    assert loaded.launcher.always_on_top is True


def test_config_save_is_atomic_and_cleans_temp_file_on_replace_failure(
    temp_config_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AppConfig(roots=[RootConfig(path=tmp_path / "docs")])
    original.save(temp_config_path)
    before = temp_config_path.read_text(encoding="utf-8")

    updated = AppConfig(
        launcher=original.launcher.model_copy(update={"hotkey": "ctrl+alt+space"}),
        roots=[RootConfig(path=tmp_path / "next-docs")],
    )

    def fail_replace(source: str | bytes | Path, destination: str | bytes | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("eodinga.config.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        updated.save(temp_config_path)

    assert temp_config_path.read_text(encoding="utf-8") == before
    assert list(temp_config_path.parent.glob(f".{temp_config_path.name}.*.tmp")) == []


def test_default_path_ends_with_config_toml() -> None:
    assert default_path().name == "config.toml"
