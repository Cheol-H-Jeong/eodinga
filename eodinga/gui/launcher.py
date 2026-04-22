from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListView, QVBoxLayout, QWidget

from eodinga.common import QueryResult, SearchHit
from eodinga.gui.design import MOTION_DEBOUNCE_MS, SPACE_16, SPACE_8
from eodinga.gui.widgets import EmptyState, ResultItemDelegate, SearchField, StatusChip
from eodinga.gui.widgets.result_item import format_hit_html
from eodinga.observability import get_logger

SearchFn = Callable[[str, int], QueryResult]


def _default_search(query: str, limit: int) -> QueryResult:
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


class LauncherPanel(QWidget):
    results_updated = Signal(object)
    result_activated = Signal(object)
    open_containing_folder = Signal(object)
    show_properties = Signal(object)
    copy_path_requested = Signal(object)

    def __init__(self, search_fn: SearchFn | None = None, max_results: int = 200, parent=None) -> None:
        super().__init__(parent)
        self._search_fn = search_fn or _default_search
        self._max_results = max_results
        self._latest_result = QueryResult()

        self.query_field = SearchField(parent=self)
        self.result_list = QListView(self)
        self.result_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.result_list.setUniformItemSizes(False)
        self.result_list.setItemDelegate(ResultItemDelegate(self.result_list))
        self.status_chip = StatusChip("Idle", self)
        self.status_label = QLabel("0 results · 0.0 ms", self)
        self.status_label.setProperty("role", "secondary")
        self.empty_state = EmptyState("Type to search", "Recent queries and indexing progress will appear here.", self)

        self.model = ResultListModel(self)
        self.result_list.setModel(self.model)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(MOTION_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._run_query)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_8)
        layout.addWidget(self.query_field)
        layout.addWidget(self.result_list, 1)
        layout.addWidget(self.empty_state)

        footer = QHBoxLayout()
        footer.addWidget(self.status_chip)
        footer.addStretch(1)
        footer.addWidget(self.status_label)
        layout.addLayout(footer)

        self.query_field.textChanged.connect(self._schedule_query)
        self.result_list.doubleClicked.connect(lambda index: self._emit_activation(index.row()))

        self._shortcuts = [
            QShortcut(QKeySequence(Qt.Key.Key_Return), self),
            QShortcut(QKeySequence("Ctrl+Return"), self),
            QShortcut(QKeySequence("Shift+Return"), self),
            QShortcut(QKeySequence("Alt+C"), self),
        ]
        self._shortcuts[0].activated.connect(self.activate_current_result)
        self._shortcuts[1].activated.connect(self.emit_open_containing_folder)
        self._shortcuts[2].activated.connect(self.emit_show_properties)
        self._shortcuts[3].activated.connect(self.emit_copy_path)

        self._refresh_empty_state()

    def set_search_fn(self, search_fn: SearchFn) -> None:
        self._search_fn = search_fn

    def activate_current_result(self) -> None:
        index = self.result_list.currentIndex()
        row = index.row() if index.isValid() else 0
        self._emit_activation(row)

    def emit_open_containing_folder(self) -> None:
        hit = self.model.item_at(self.result_list.currentIndex().row())
        if hit is not None:
            self.open_containing_folder.emit(hit)

    def emit_show_properties(self) -> None:
        hit = self.model.item_at(self.result_list.currentIndex().row())
        if hit is not None:
            self.show_properties.emit(hit)

    def emit_copy_path(self) -> None:
        hit = self.model.item_at(self.result_list.currentIndex().row())
        if hit is not None:
            self.copy_path_requested.emit(hit)

    def _emit_activation(self, row: int) -> None:
        hit = self.model.item_at(row)
        if hit is not None:
            self.result_activated.emit(hit)

    def _schedule_query(self, _: str) -> None:
        self._debounce_timer.start()

    def _run_query(self) -> None:
        query = self.query_field.text().strip()
        self._latest_result = self._search_fn(query, self._max_results)
        self.model.set_items(self._latest_result.items, query)
        self.status_label.setText(f"{self._latest_result.total} results · {self._latest_result.elapsed_ms:.1f} ms")
        self.status_chip.setText("Ready" if query else "Idle")
        if self.model.rowCount() > 0:
            self.result_list.setCurrentIndex(cast(QModelIndex, self.model.index(0, 0)))
        self._refresh_empty_state()
        self.results_updated.emit(self._latest_result)
        get_logger().debug("launcher query '{}' returned {}", query, self._latest_result.total)

    def _refresh_empty_state(self) -> None:
        has_results = self.model.rowCount() > 0
        self.empty_state.setVisible(not has_results)
        self.result_list.setVisible(has_results)


class LauncherWindow(LauncherPanel):
    def __init__(self, search_fn: SearchFn | None = None, max_results: int = 200, parent=None) -> None:
        super().__init__(search_fn=search_fn, max_results=max_results, parent=parent)
        self.setObjectName("surface")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(640, 480)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)
