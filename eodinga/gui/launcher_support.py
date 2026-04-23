from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.widgets.result_item import format_hit_html


def default_search(query: str, limit: int) -> QueryResult:
    hit = SearchHit(
        path=Path("/tmp/example.txt"),
        parent_path=Path("/tmp"),
        name="example.txt",
        ext="txt",
        highlighted_name="example.txt",
        highlighted_path="/tmp/example.txt",
    )
    items = [hit] if query else []
    return QueryResult(items=items[:limit], total=len(items), elapsed_ms=2.0)


def format_indexing_status(status: IndexingStatus) -> str:
    if status.phase != "indexing":
        return "Indexing idle. Results update automatically when your roots change."
    total = str(status.total_files) if status.total_files > 0 else "?"
    progress = ""
    if status.total_files > 0:
        percent = round((status.processed_files / status.total_files) * 100)
        progress = f" ({percent}%)"
    root_label = f" in {status.current_root}" if status.current_root is not None else ""
    return f"Indexing {status.processed_files}/{total} files{progress}{root_label}."


def format_indexing_footer(status: IndexingStatus) -> str:
    if status.phase != "indexing":
        return "0 results · 0.0 ms"
    total = str(status.total_files) if status.total_files > 0 else "?"
    parts = [f"{status.processed_files}/{total} files"]
    if status.total_files > 0:
        percent = round((status.processed_files / status.total_files) * 100)
        parts.append(f"{percent}% indexed")
    else:
        parts.append("indexing")
    return " · ".join(parts)


class ResultListModel(QAbstractListModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[SearchHit] = []
        self._query = ""

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return format_hit_html(item, self._query)
        if role == Qt.ItemDataRole.UserRole:
            return item
        return None

    def set_items(self, items: list[SearchHit], query: str) -> None:
        self.beginResetModel()
        self._items = items
        self._query = query
        self.endResetModel()

    def item_at(self, row: int) -> SearchHit | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None
