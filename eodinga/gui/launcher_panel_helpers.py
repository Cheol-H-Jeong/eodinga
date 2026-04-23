from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QListView

from eodinga.common import SearchHit
from eodinga.gui.launcher_state import ResultListModel


def emit_if_hit(hit: SearchHit | None, emit: Callable[[SearchHit], None]) -> None:
    if hit is not None:
        emit(hit)


def ensure_result_selection(result_list: QListView, model: ResultListModel) -> None:
    if not result_list.currentIndex().isValid() and model.rowCount() > 0:
        result_list.setCurrentIndex(cast(QModelIndex, model.index(0, 0)))
