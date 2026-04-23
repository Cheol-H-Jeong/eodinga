from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QEvent, QModelIndex, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListView, QVBoxLayout, QWidget

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.design import MOTION_DEBOUNCE_MS, SPACE_16, SPACE_8
from eodinga.gui.launcher_navigation import handle_query_field_keypress, handle_result_list_keypress
from eodinga.gui.launcher_result_menu import build_launcher_result_menu
from eodinga.gui.launcher_strings import (
    build_launcher_empty_state,
    build_launcher_shortcut_hint,
    build_result_list_accessible_description,
)
from eodinga.gui.launcher_state import LauncherState, ResultListModel, default_search, format_indexing_footer
from eodinga.gui.widgets import (
    ActiveFilterRow,
    EmptyState,
    LauncherActionBar,
    LauncherPreviewPane,
    QueryChipRow,
    ResultItemDelegate,
    SearchField,
    StatusChip,
)
from eodinga.observability import get_logger

SearchFn = Callable[[str, int], QueryResult]


class LauncherPanel(QWidget):
    results_updated = Signal(object)
    result_activated = Signal(object)
    open_containing_folder = Signal(object)
    show_properties = Signal(object)
    copy_path_requested = Signal(object)
    copy_name_requested = Signal(object)
    def __init__(
        self,
        search_fn: SearchFn | None = None,
        max_results: int = 200,
        debounce_ms: int = MOTION_DEBOUNCE_MS,
        state: LauncherState | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher panel")
        self._search_fn = search_fn or default_search
        self._max_results = max_results
        self._latest_result = QueryResult()
        self._recent_queries: list[str] = []
        self._pinned_queries: list[str] = []
        self._indexing_status = IndexingStatus()
        self._state = state
        self._history_index: int | None = None
        self._history_draft = ""
        self._applying_history_query = False
        self._skip_remember_query = False

        self.query_field = SearchField(parent=self)
        self.query_field.setAccessibleName("Launcher search field")
        self.active_filter_row = ActiveFilterRow(self)
        self.pinned_queries_row = QueryChipRow(
            "Pinned",
            accessible_name="Pinned launcher queries",
            on_chip_clicked=self._apply_query_chip,
            parent=self,
        )
        self.recent_queries_row = QueryChipRow(
            "Recent",
            accessible_name="Recent launcher queries",
            on_chip_clicked=self._apply_query_chip,
            parent=self,
        )
        self.result_list = QListView(self)
        self.result_list.setAccessibleName("Launcher results list")
        self.result_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.result_list.setUniformItemSizes(False)
        self.result_list.setItemDelegate(ResultItemDelegate(self.result_list))
        self.result_list.setMouseTracking(True)
        self.result_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.status_chip = StatusChip("Idle", self)
        self.shortcut_label = QLabel("", self)
        self.shortcut_label.setProperty("role", "secondary")
        self.shortcut_label.setAccessibleName("Launcher shortcut guidance")
        self.status_label = QLabel("0 results · 0.0 ms", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setAccessibleName("Launcher result summary")
        self.empty_state = EmptyState("Type to search", "Recent queries and indexing progress will appear here.", self)
        self.preview_pane = LauncherPreviewPane(self)
        self.preview_pane.setMinimumWidth(240)
        self.action_bar = LauncherActionBar(self)

        self.model = ResultListModel(self)
        self.result_list.setModel(self.model)
        self.result_list.selectionModel().currentChanged.connect(self._sync_preview_to_current_index)
        self.result_list.entered.connect(self._handle_hovered_index)
        self.result_list.customContextMenuRequested.connect(self._show_result_context_menu)
        self.preview_pane.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview_pane.customContextMenuRequested.connect(self._show_preview_context_menu)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(debounce_ms)
        self._debounce_timer.timeout.connect(self._run_query)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_8)
        layout.addWidget(self.query_field)
        layout.addWidget(self.active_filter_row)
        layout.addWidget(self.pinned_queries_row)
        layout.addWidget(self.recent_queries_row)

        content = QHBoxLayout()
        content.setSpacing(SPACE_16)
        content_column = QVBoxLayout()
        content_column.setContentsMargins(0, 0, 0, 0)
        content_column.setSpacing(SPACE_8)
        content_column.addWidget(self.result_list, 1)
        content_column.addWidget(self.empty_state)
        content.addLayout(content_column, 3)

        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(SPACE_8)
        sidebar.addWidget(self.preview_pane, 1)
        sidebar.addWidget(self.action_bar)
        content.addLayout(sidebar, 2)
        layout.addLayout(content, 1)

        footer = QHBoxLayout()
        footer.addWidget(self.status_chip)
        footer.addWidget(self.shortcut_label)
        footer.addStretch(1)
        footer.addWidget(self.status_label)
        layout.addLayout(footer)

        self.query_field.textChanged.connect(self._schedule_query)
        self.query_field.textChanged.connect(self.active_filter_row.set_query)
        self.query_field.textChanged.connect(self.preview_pane.set_query)
        self.result_list.doubleClicked.connect(lambda index: self._emit_activation(index.row()))
        self.query_field.installEventFilter(self)
        self.result_list.installEventFilter(self)

        self._shortcuts = [
            QShortcut(QKeySequence(Qt.Key.Key_Return), self),
            QShortcut(QKeySequence("Ctrl+Return"), self),
            QShortcut(QKeySequence("Shift+Return"), self),
            QShortcut(QKeySequence("Alt+C"), self),
            QShortcut(QKeySequence("Alt+N"), self),
            QShortcut(QKeySequence(QKeySequence.StandardKey.SelectAll), self),
            QShortcut(QKeySequence("Ctrl+L"), self),
            QShortcut(QKeySequence("Alt+Up"), self),
            QShortcut(QKeySequence("Alt+Down"), self),
            QShortcut(QKeySequence("Shift+F10"), self),
            QShortcut(QKeySequence(Qt.Key.Key_Menu), self),
        ]
        self._shortcuts[0].activated.connect(self.activate_current_result)
        self._shortcuts[1].activated.connect(self.emit_open_containing_folder)
        self._shortcuts[2].activated.connect(self.emit_show_properties)
        self._shortcuts[3].activated.connect(self.emit_copy_path)
        self._shortcuts[4].activated.connect(self.emit_copy_name)
        self._shortcuts[5].activated.connect(self.select_query_text)
        self._shortcuts[6].activated.connect(self.focus_query_field)
        self._shortcuts[7].activated.connect(self.recall_previous_query)
        self._shortcuts[8].activated.connect(self.recall_next_query)
        self._shortcuts[9].activated.connect(self.show_current_result_menu)
        self._shortcuts[10].activated.connect(self.show_current_result_menu)
        self.action_bar.open_button.clicked.connect(self.activate_current_result)
        self.action_bar.reveal_button.clicked.connect(self.emit_open_containing_folder)
        self.action_bar.copy_path_button.clicked.connect(self.emit_copy_path)
        self.action_bar.copy_name_button.clicked.connect(self.emit_copy_name)
        self.action_bar.properties_button.clicked.connect(self.emit_show_properties)
        self._quick_pick_shortcuts: list[QShortcut] = []
        for index in range(9):
            shortcut = QShortcut(QKeySequence(f"Alt+{index + 1}"), self)
            shortcut.activated.connect(lambda row=index: self.activate_result_at(row))
            self._quick_pick_shortcuts.append(shortcut)
        if self._state is not None:
            self._state.recent_queries_changed.connect(self.set_recent_queries)
            self._state.pinned_queries_changed.connect(self.set_pinned_queries)
            self._state.indexing_status_changed.connect(self.set_indexing_status)
            self.set_recent_queries(self._state.recent_queries)
            self.set_pinned_queries(self._state.pinned_queries)
            self.set_indexing_status(self._state.indexing_status)

        self._refresh_empty_state()
        self._refresh_shortcut_hint()
        self.active_filter_row.set_query(self.query_field.text())
        self._refresh_preview()
        self._refresh_result_list_accessibility()

    def set_search_fn(self, search_fn: SearchFn) -> None:
        self._search_fn = search_fn

    def set_recent_queries(self, queries: list[str]) -> None:
        self._recent_queries = queries
        self.recent_queries_row.set_queries(queries[:5])
        self._refresh_empty_state()

    def set_pinned_queries(self, queries: list[str]) -> None:
        self._pinned_queries = queries
        self.pinned_queries_row.set_queries(queries[:5])
        self._refresh_empty_state()

    def set_indexing_status(self, status: IndexingStatus) -> None:
        self._indexing_status = status
        self._refresh_status_footer()
        self._refresh_empty_state()

    def activate_current_result(self) -> None:
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            self.result_activated.emit(hit)

    def activate_result_at(self, row: int) -> None:
        self._flush_pending_query()
        hit = self.model.item_at(row)
        if hit is None:
            return
        self._set_selection(row)
        self.result_activated.emit(hit)

    def focus_query_field(self) -> None:
        self.query_field.setFocus()
        self.query_field.selectAll()

    def select_query_text(self) -> None:
        self.focus_query_field()

    def emit_open_containing_folder(self) -> None:
        self._emit_hit_signal(self.open_containing_folder)

    def emit_show_properties(self) -> None:
        self._emit_hit_signal(self.show_properties)

    def emit_copy_path(self) -> None:
        self._emit_hit_signal(self.copy_path_requested)

    def emit_copy_name(self) -> None:
        self._emit_hit_signal(self.copy_name_requested)

    def recall_previous_query(self) -> None:
        self._navigate_recent_queries(-1)

    def recall_next_query(self) -> None:
        self._navigate_recent_queries(1)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in {self.query_field, self.result_list} and event.type() == QEvent.Type.FocusIn:
            self._refresh_shortcut_hint()
        if watched in {self.query_field, self.result_list} and event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._refresh_shortcut_hint)
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key_event = cast(QKeyEvent, event)
        if watched is self.query_field:
            return self._handle_query_field_keypress(key_event)
        if watched is self.result_list:
            return self._handle_result_list_keypress(key_event)
        return super().eventFilter(watched, event)

    def _emit_activation(self, row: int) -> None:
        hit = self.model.item_at(row)
        if hit is not None:
            self.result_activated.emit(hit)

    def _schedule_query(self, _: str) -> None:
        if not self._applying_history_query:
            self._history_index = None
            self._history_draft = ""
        self._debounce_timer.start()

    def _flush_pending_query(self) -> None:
        if not self._debounce_timer.isActive():
            return
        self._debounce_timer.stop()
        self._run_query()

    def _run_query(self) -> None:
        query = self.query_field.text().strip()
        previous_hit = self._current_hit()
        self._latest_result = self._search_fn(query, self._max_results)
        if self._state is not None and query and not self._skip_remember_query:
            self._state.remember_query(query)
        self._skip_remember_query = False
        self.model.set_items(self._latest_result.items, query)
        self._refresh_status_footer()
        self._restore_selection(previous_hit)
        self._refresh_empty_state()
        self._refresh_shortcut_hint()
        self._refresh_preview()
        self._refresh_result_list_accessibility()
        self.results_updated.emit(self._latest_result)
        get_logger().debug("launcher query '{}' returned {}", query, self._latest_result.total)

    def _refresh_status_footer(self) -> None:
        query = self.query_field.text().strip()
        if not query:
            if self._indexing_status.phase == "indexing":
                self.status_chip.setText("Indexing")
                self.status_label.setText(format_indexing_footer(self._indexing_status))
            else:
                self.status_chip.setText("Idle")
                self.status_label.setText("0 results · 0.0 ms")
            return
        self.status_label.setText(f"{self._latest_result.total} results · {self._latest_result.elapsed_ms:.1f} ms")
        if self._latest_result.total > 0:
            self.status_chip.setText("Ready")
        else:
            self.status_chip.setText("No results")

    def _refresh_empty_state(self) -> None:
        has_results = self.model.rowCount() > 0
        query = self.query_field.text().strip()
        title, body, details = build_launcher_empty_state(query, self._recent_queries, self._pinned_queries, self._indexing_status)
        self.empty_state.set_content(title, body, details)
        self.empty_state.setVisible(not has_results)
        self.result_list.setVisible(has_results)

    def _refresh_shortcut_hint(self) -> None:
        self.shortcut_label.setText(
            build_launcher_shortcut_hint(
                has_results=self.model.rowCount() > 0,
                result_list_has_focus=self.result_list.hasFocus(),
                has_query=bool(self.query_field.text().strip()),
            )
        )

    def _current_hit(self) -> SearchHit | None:
        index = self.result_list.currentIndex()
        row = index.row() if index.isValid() else 0
        return self.model.item_at(row)

    def _handle_query_field_keypress(self, event: QKeyEvent) -> bool:
        return handle_query_field_keypress(self, event)

    def _handle_result_list_keypress(self, event: QKeyEvent) -> bool:
        return handle_result_list_keypress(self, event)

    def _move_selection(self, delta: int, *, wrap: bool = False) -> None:
        if self.model.rowCount() == 0:
            return
        current_row = self.result_list.currentIndex().row()
        if current_row < 0:
            current_row = 0
        if wrap:
            next_row = (current_row + delta) % self.model.rowCount()
        else:
            next_row = min(max(current_row + delta, 0), self.model.rowCount() - 1)
        self._set_selection(next_row)

    def _page_step(self) -> int:
        return min(max(self.model.rowCount() // 2, 1), 10)

    def _restore_selection(self, previous_hit: SearchHit | None) -> None:
        if self.model.rowCount() == 0:
            return
        if previous_hit is not None:
            for row, item in enumerate(self._latest_result.items):
                if item.path == previous_hit.path:
                    self._set_selection(row)
                    return
        self._set_selection(0)

    def _set_selection(self, row: int) -> None:
        self.result_list.setCurrentIndex(cast(QModelIndex, self.model.index(row, 0)))
        self.result_list.scrollTo(self.result_list.currentIndex())
        self._refresh_result_list_accessibility()

    def _sync_preview_to_current_index(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        self._sync_preview_to_index(current)

    def _handle_hovered_index(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        self._set_selection(index.row())

    def _emit_hit_signal(self, signal: Any) -> None:
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            signal.emit(hit)

    def show_current_result_menu(self) -> None:
        menu = self._build_current_result_menu(self)
        if menu is None:
            return
        row = self.result_list.currentIndex().row()
        item_rect = self.result_list.visualRect(self.model.index(max(row, 0), 0))
        origin = item_rect.center() if item_rect.isValid() else self.rect().center()
        menu.popup(self.mapToGlobal(origin))

    def _show_result_context_menu(self, position) -> None:
        index = self.result_list.indexAt(position)
        if index.isValid():
            self._set_selection(index.row())
        self._exec_current_result_menu(self.result_list, self.result_list.viewport().mapToGlobal(position))

    def _show_preview_context_menu(self, position) -> None:
        self._exec_current_result_menu(self.preview_pane, self.preview_pane.mapToGlobal(position))

    def _exec_current_result_menu(self, parent: QWidget, global_position) -> None:
        menu = self._build_current_result_menu(parent)
        if menu is not None:
            menu.exec(global_position)

    def _build_current_result_menu(self, parent: QWidget):
        return build_launcher_result_menu(
            parent,
            self._current_hit(),
            open_result=self.activate_current_result,
            reveal_result=self.emit_open_containing_folder,
            copy_path=self.emit_copy_path,
            copy_name=self.emit_copy_name,
            show_properties=self.emit_show_properties,
        )

    def _sync_preview_to_index(self, index: QModelIndex) -> None:
        current_hit = self.model.item_at(index.row()) if index.isValid() else None
        self.preview_pane.set_hit(current_hit)
        self.action_bar.set_enabled(index.isValid())
        self.action_bar.set_context(current_hit)
        self._refresh_result_list_accessibility()

    def _refresh_preview(self) -> None:
        self._sync_preview_to_index(self.result_list.currentIndex())

    def _refresh_result_list_accessibility(self) -> None:
        count = self.model.rowCount()
        current_hit = self._current_hit()
        self.result_list.setAccessibleDescription(
            build_result_list_accessible_description(
                count,
                max(self.result_list.currentIndex().row(), 0) + 1 if current_hit is not None else None,
                current_hit.name if current_hit is not None else None,
            )
        )

    def _navigate_recent_queries(self, direction: int) -> None:
        if not self._recent_queries:
            return
        if direction < 0:
            if self._history_index is None:
                self._history_draft = self.query_field.text()
                next_index = 0
            else:
                next_index = min(self._history_index + 1, len(self._recent_queries) - 1)
        else:
            if self._history_index is None:
                return
            if self._history_index == 0:
                self._history_index = None
                self._set_query_from_history(self._history_draft)
                self._history_draft = ""
                return
            next_index = self._history_index - 1
        self._history_index = next_index
        self._set_query_from_history(self._recent_queries[next_index])

    def _set_query_from_history(self, query: str) -> None:
        self._applying_history_query = True
        try:
            self._skip_remember_query = True
            self.query_field.setFocus()
            self.query_field.setText(query)
            self.query_field.setCursorPosition(len(query))
        finally:
            self._applying_history_query = False

    def _apply_query_chip(self, query: str) -> None:
        self.query_field.setFocus()
        self._set_query_from_history(query)
        self._flush_pending_query()
