from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def parser_fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "parsers"
