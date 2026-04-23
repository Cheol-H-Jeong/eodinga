from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt, Signal

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.widgets.result_item import format_hit_accessible_text, format_hit_html


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


class LauncherState(QObject):
    recent_queries_changed = Signal(list)
    pinned_queries_changed = Signal(list)
    indexing_status_changed = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        recent_queries: list[str] | None = None,
        pinned_queries: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._recent_queries: deque[str] = deque(self._normalize_queries(recent_queries or [])[:5], maxlen=5)
        self._pinned_queries = self._normalize_queries(pinned_queries or [])
        self._indexing_status = IndexingStatus()

    @property
    def recent_queries(self) -> list[str]:
        return list(self._recent_queries)

    @property
    def indexing_status(self) -> IndexingStatus:
        return self._indexing_status

    @property
    def pinned_queries(self) -> list[str]:
        return list(self._pinned_queries)

    def remember_query(self, query: str) -> None:
        normalized = query.strip()
        if not normalized:
            return
        items = [item for item in self._recent_queries if item != normalized]
        items.insert(0, normalized)
        self._recent_queries = deque(items[: self._recent_queries.maxlen], maxlen=self._recent_queries.maxlen)
        self.recent_queries_changed.emit(self.recent_queries)

    def set_pinned_queries(self, queries: list[str]) -> None:
        normalized = self._normalize_queries(queries)
        if normalized == self._pinned_queries:
            return
        self._pinned_queries = normalized
        self.pinned_queries_changed.emit(self.pinned_queries)

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self._indexing_status = status
        self.indexing_status_changed.emit(status)

    @staticmethod
    def _normalize_queries(queries: list[str]) -> list[str]:
        normalized: list[str] = []
        for query in queries:
            stripped = query.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized


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
        quick_pick_number = index.row() + 1
        if role == Qt.ItemDataRole.DisplayRole:
            return format_hit_html(item, self._query, quick_pick_number=quick_pick_number)
        if role == Qt.ItemDataRole.ToolTipRole:
            return format_hit_accessible_text(item, self._query, quick_pick_number=quick_pick_number)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return format_hit_accessible_text(item, self._query, quick_pick_number=quick_pick_number)
        if role == Qt.ItemDataRole.AccessibleDescriptionRole:
            return f"Result {index.row() + 1} of {len(self._items)}."
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
