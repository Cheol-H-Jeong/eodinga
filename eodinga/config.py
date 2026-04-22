from __future__ import annotations

import os
import sys
import tempfile
import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict, Field


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write_text(path: Path, contents: str) -> None:
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    temp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _fsync_directory(directory)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


class GeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str = "system"
    language: str = "auto"


class LauncherConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hotkey: str = "ctrl+shift+space"
    debounce_ms: int = 30
    max_results: int = 200
    window_x: int | None = None
    window_y: int | None = None
    window_width: int = 640
    window_height: int = 480


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
        payload = {
            "general": self.general.model_dump(mode="json"),
            "launcher": self.launcher.model_dump(mode="json", exclude_none=True),
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
        _atomic_write_text(target, tomli_w.dumps(payload))


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


def _migrate_legacy_config(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    migrated = dict(raw)
    launcher = migrated.get("launcher")
    if isinstance(launcher, dict):
        migrated_launcher = dict(launcher)
        migrated_launcher.pop("always_on_top", None)
        migrated["launcher"] = migrated_launcher
    return migrated


def load(path: Path | None = None) -> AppConfig:
    config_path = path.expanduser() if path is not None else default_path()
    if not config_path.exists():
        return AppConfig()
    raw = _migrate_legacy_config(tomllib.loads(config_path.read_text(encoding="utf-8")))
    return AppConfig.model_validate(raw)
