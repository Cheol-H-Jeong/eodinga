from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict, Field


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


class GeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str = "system"
    language: str = "auto"


class LauncherConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hotkey: str = "ctrl+shift+space"
    debounce_ms: int = 30
    max_results: int = 200


class IndexConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: Path = Field(default_factory=lambda: default_db_path())
    content_enabled: bool = True
    parser_timeout_s: int = 10
    parser_max_bytes: int = 50 * 1024 * 1024
    parser_workers: int = 0


class RootConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    include: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
        ]
    )


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    launcher: LauncherConfig = Field(default_factory=LauncherConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    roots: list[RootConfig] = Field(default_factory=list)

    def save(self, path: Path) -> None:
        target = path.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "general": self.general.model_dump(mode="json"),
            "launcher": self.launcher.model_dump(mode="json"),
            "index": {
                **self.index.model_dump(mode="json"),
                "db_path": str(self.index.db_path),
            },
            "roots": [
                {
                    "path": str(root.path),
                    "include": root.include,
                    "exclude": root.exclude,
                }
                for root in self.roots
            ],
        }
        target.write_text(tomli_w.dumps(payload), encoding="utf-8")


def default_config_dir() -> Path:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "eodinga"
        return Path.home() / "AppData" / "Roaming" / "eodinga"
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "eodinga"
    return Path.home() / ".config" / "eodinga"


def default_data_dir() -> Path:
    if sys.platform.startswith("win"):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "eodinga"
        return Path.home() / "AppData" / "Local" / "eodinga"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "eodinga"
    return Path.home() / ".local" / "share" / "eodinga"


def default_db_path() -> Path:
    return default_data_dir() / "index.db"


def default_path() -> Path:
    return default_config_dir() / "config.toml"


def load(path: Path | None = None) -> AppConfig:
    config_path = path.expanduser() if path is not None else default_path()
    if not config_path.exists():
        return AppConfig()
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(raw)

