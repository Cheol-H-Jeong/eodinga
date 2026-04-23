from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QModelIndex, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListView, QSizePolicy, QVBoxLayout, QWidget
from shiboken6 import isValid

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.design import MOTION_DEBOUNCE_MS, SPACE_16, SPACE_8
from eodinga.gui.launcher_state import LauncherState, ResultListModel, default_search, format_indexing_footer, format_indexing_status
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
        self.status_chip = StatusChip("Idle", self)
        self.shortcut_label = QLabel("", self)
        self.shortcut_label.setProperty("role", "secondary")
        self.shortcut_label.setAccessibleName("Launcher shortcut guidance")
        self.shortcut_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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
        self._refresh_query_field_accessibility()
        self.active_filter_row.set_query(self.query_field.text())
        self._refresh_preview()
        self._refresh_result_list_accessibility()
        self._install_auxiliary_event_filters()

    def set_search_fn(self, search_fn: SearchFn) -> None:
        self._search_fn = search_fn

    def set_recent_queries(self, queries: list[str]) -> None:
        self._recent_queries = queries
        self.recent_queries_row.set_queries(queries[:5])
        self._install_auxiliary_event_filters()
        self._refresh_empty_state()
        self._refresh_query_field_accessibility()

    def set_pinned_queries(self, queries: list[str]) -> None:
        self._pinned_queries = queries
        self.pinned_queries_row.set_queries(queries[:5])
        self._install_auxiliary_event_filters()
        self._refresh_empty_state()
        self._refresh_query_field_accessibility()

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
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            self.open_containing_folder.emit(hit)

    def emit_show_properties(self) -> None:
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            self.show_properties.emit(hit)

    def emit_copy_path(self) -> None:
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            self.copy_path_requested.emit(hit)

    def emit_copy_name(self) -> None:
        self._flush_pending_query()
        hit = self._current_hit()
        if hit is not None:
            self.copy_name_requested.emit(hit)

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
        if watched in self._chip_buttons():
            return self._handle_chip_keypress(cast(QWidget, watched), key_event)
        if watched in self._action_buttons():
            return self._handle_action_button_keypress(cast(QWidget, watched), key_event)
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
        if self._state_is_available() and query and not self._skip_remember_query:
            state = self._state
            if state is not None:
                state.remember_query(query)
        self._skip_remember_query = False
        self.model.set_items(self._latest_result.items, query)
        self._refresh_status_footer()
        self._restore_selection(previous_hit)
        self._refresh_empty_state()
        self._refresh_shortcut_hint()
        self._refresh_query_field_accessibility()
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
        details = format_indexing_status(self._indexing_status)
        if not query:
            recent_queries = ", ".join(self._recent_queries[:3]) if self._recent_queries else "No recent queries yet."
            pinned_queries = f" Pinned: {', '.join(self._pinned_queries[:3])}." if self._pinned_queries else ""
            self.empty_state.set_content(
                "Type to search",
                (
                    f"Recent: {recent_queries}.{pinned_queries} Click a launcher chip or use Alt+Up and Alt+Down for history. "
                    "Tab cycles chips, results, and actions, Shift+Tab reverses, Alt+1 through Alt+9 opens a top hit, "
                    "Enter opens it, and Ctrl+Enter reveals its folder."
                ),
                details,
            )
        else:
            self.empty_state.set_content(
                f'No results for "{query}"',
                (
                    "Try another term or refine with ext:pdf, date:this-week, or size:>10M. "
                    "Use Alt+Up and Alt+Down for recent queries, Tab or Shift+Tab for chips, or Esc to hide the launcher."
                ),
                details,
            )
        self.empty_state.setVisible(not has_results)
        self.result_list.setVisible(has_results)

    def _refresh_shortcut_hint(self) -> None:
        has_results = self.model.rowCount() > 0
        if not has_results:
            if self.query_field.text().strip():
                hint = (
                    "Refine with ext:, date:, size:, or content:. Tab reviews launcher chips. Alt+Up and Alt+Down browse recent queries."
                )
            else:
                hint = (
                    "Type a filename, path, or content term. Tab reviews launcher chips. Alt+Up and Alt+Down browse recent queries."
                )
        elif self.result_list.hasFocus():
            hint = (
                "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. "
                "Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Tab moves to actions. Shift+Tab returns to filters. Ctrl+A or Ctrl+L returns to filter."
            )
        else:
            hint = (
                "Tab cycles through chips, results, and actions. Shift+Tab reverses. Down/Up navigate. Home/End and PgUp/PgDn jump. "
                "Enter opens the top hit. Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. "
                "Alt+Up and Alt+Down browse recent queries."
            )
        self.shortcut_label.setText(hint)

    def _current_hit(self) -> SearchHit | None:
        index = self.result_list.currentIndex()
        row = index.row() if index.isValid() else 0
        return self.model.item_at(row)

    def _handle_query_field_keypress(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Tab:
            return self._focus_first_secondary_target()
        if event.key() == Qt.Key.Key_Backtab:
            return self._focus_last_secondary_target()
        if self.model.rowCount() == 0:
            return False
        if event.key() == Qt.Key.Key_Down:
            self.result_list.setFocus()
            if not self.result_list.currentIndex().isValid():
                self._set_selection(0)
            else:
                self._move_selection(1)
            return True
        if event.key() == Qt.Key.Key_Up:
            self.result_list.setFocus()
            if not self.result_list.currentIndex().isValid():
                self._set_selection(self.model.rowCount() - 1)
            else:
                self._move_selection(-1)
            return True
        if event.key() == Qt.Key.Key_Home:
            self.result_list.setFocus()
            self._set_selection(0)
            return True
        if event.key() == Qt.Key.Key_End:
            self.result_list.setFocus()
            self._set_selection(self.model.rowCount() - 1)
            return True
        if event.key() == Qt.Key.Key_PageDown:
            self.result_list.setFocus()
            self._move_selection(self._page_step())
            return True
        if event.key() == Qt.Key.Key_PageUp:
            self.result_list.setFocus()
            self._move_selection(-self._page_step())
            return True
        return False

    def _handle_result_list_keypress(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Tab:
            return self._focus_first_action_button()
        if event.key() == Qt.Key.Key_Backtab:
            if self._focus_last_chip_button():
                return True
            self.query_field.setFocus()
            return True
        if event.key() == Qt.Key.Key_Down:
            self._move_selection(1, wrap=True)
            return True
        if event.key() == Qt.Key.Key_Up:
            self._move_selection(-1, wrap=True)
            return True
        if event.key() == Qt.Key.Key_Home:
            self._set_selection(0)
            return True
        if event.key() == Qt.Key.Key_End:
            self._set_selection(self.model.rowCount() - 1)
            return True
        if event.key() == Qt.Key.Key_PageDown:
            self._move_selection(self._page_step())
            return True
        if event.key() == Qt.Key.Key_PageUp:
            self._move_selection(-self._page_step())
            return True
        return False

    def _handle_chip_keypress(self, watched: QWidget, event: QKeyEvent) -> bool:
        buttons = self._chip_buttons()
        if not buttons:
            return False
        if event.key() == Qt.Key.Key_Tab:
            current_index = buttons.index(watched)
            if current_index + 1 < len(buttons):
                buttons[current_index + 1].setFocus()
                return True
            if self._focus_results_list():
                return True
            return self._focus_first_action_button()
        if event.key() == Qt.Key.Key_Backtab:
            current_index = buttons.index(watched)
            if current_index > 0:
                buttons[current_index - 1].setFocus()
                return True
            self.query_field.setFocus()
            return True
        return False

    def _handle_action_button_keypress(self, watched: QWidget, event: QKeyEvent) -> bool:
        buttons = self._action_buttons()
        if not buttons:
            return False
        if event.key() == Qt.Key.Key_Tab:
            current_index = buttons.index(watched)
            if current_index + 1 < len(buttons):
                buttons[current_index + 1].setFocus()
                return True
            self.query_field.setFocus()
            return True
        if event.key() == Qt.Key.Key_Backtab:
            current_index = buttons.index(watched)
            if current_index > 0:
                buttons[current_index - 1].setFocus()
                return True
            if self._focus_results_list():
                return True
            if self._focus_last_chip_button():
                return True
            self.query_field.setFocus()
            return True
        return False

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

    def _refresh_query_field_accessibility(self) -> None:
        description_parts = ["Type a filename, path, or content term to search the index."]
        chip_count = len(self._chip_buttons())
        if chip_count:
            description_parts.append(f"{chip_count} launcher history chips are available from the search field with Tab.")
        if self.model.rowCount() > 0:
            description_parts.append("Tab moves through chips, results, and action buttons; Shift+Tab reverses.")
        self.query_field.setAccessibleDescription(" ".join(description_parts))

    def _install_auxiliary_event_filters(self) -> None:
        for widget in [*self._chip_buttons(), *self._action_buttons()]:
            widget.installEventFilter(self)

    def _state_is_available(self) -> bool:
        return self._state is not None and isValid(self._state)

    def _chip_buttons(self) -> list[QWidget]:
        return [*self.pinned_queries_row.buttons, *self.recent_queries_row.buttons]

    def _action_buttons(self) -> list[QWidget]:
        buttons = [
            self.action_bar.open_button,
            self.action_bar.reveal_button,
            self.action_bar.copy_path_button,
            self.action_bar.copy_name_button,
            self.action_bar.properties_button,
        ]
        return [button for button in buttons if button.isEnabled()]

    def _focus_first_secondary_target(self) -> bool:
        if self._focus_first_chip_button():
            return True
        if self._focus_results_list():
            return True
        return self._focus_first_action_button()

    def _focus_last_secondary_target(self) -> bool:
        if self._focus_last_chip_button():
            return True
        return self._focus_results_list()

    def _focus_first_chip_button(self) -> bool:
        buttons = self._chip_buttons()
        if not buttons:
            return False
        buttons[0].setFocus()
        return True

    def _focus_last_chip_button(self) -> bool:
        buttons = self._chip_buttons()
        if not buttons:
            return False
        buttons[-1].setFocus()
        return True

    def _focus_results_list(self) -> bool:
        if self.model.rowCount() == 0:
            return False
        self.result_list.setFocus()
        current_index = self.result_list.currentIndex()
        if not current_index.isValid():
            self.result_list.setCurrentIndex(cast(QModelIndex, self.model.index(0, 0)))
        return True

    def _focus_first_action_button(self) -> bool:
        buttons = self._action_buttons()
        if not buttons:
            return False
        buttons[0].setFocus()
        return True

    def _focus_last_action_button(self) -> bool:
        buttons = self._action_buttons()
        if not buttons:
            return False
        buttons[-1].setFocus()
        return True

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
        if count == 0:
            self.result_list.setAccessibleDescription("No launcher results are available.")
            return
        current_hit = self._current_hit()
        description = f"{count} launcher results."
        if current_hit is not None:
            current_row = max(self.result_list.currentIndex().row(), 0) + 1
            description = f"{description} Selected {current_row} of {count}: {current_hit.name}."
        self.result_list.setAccessibleDescription(
            f"{description} Use Up and Down to move between results, Enter to open, Tab to reach result actions, Shift+Tab to return to filters, and Alt+1 through Alt+9 for quick picks."
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
