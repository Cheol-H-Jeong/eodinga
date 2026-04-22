from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture()
def temp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"


@pytest.fixture()
def cli_runner(tmp_path: Path) -> Iterator[Callable[..., subprocess.CompletedProcess[str]]]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "eodinga", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    yield run


@pytest.fixture()
def parse_json_output() -> Callable[[str], dict[str, object]]:
    def parse(output: str) -> dict[str, object]:
        return json.loads(output)

    return parse
