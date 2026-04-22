from __future__ import annotations

import os
import sys
from typing import Generator, cast

import pytest
from PySide6.QtWidgets import QApplication


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp() -> Generator[QApplication, None, None]:
    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    yield app
