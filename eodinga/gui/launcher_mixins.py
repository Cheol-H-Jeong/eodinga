from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from eodinga.gui.widgets import QueryChipRow, SecondaryButton


class LauncherInteractionMixin:
    def _host(self) -> Any:
        return cast(Any, self)

    def _emit_activation(self, row: int) -> None:
        host = self._host()
        hit = host.model.item_at(row)
        if hit is not None:
            host.result_activated.emit(hit)

    def _schedule_query(self, _: str) -> None:
        host = self._host()
        if not host._applying_history_query:
            host._history_index = None
            host._history_draft = ""
        host._debounce_timer.start()

    def _flush_pending_query(self) -> None:
        host = self._host()
        if not host._debounce_timer.isActive():
            return
        host._debounce_timer.stop()
        host._run_query()

    def _sync_preview_to_current_index(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        self._sync_preview_to_index(current)

    def _handle_hovered_index(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        self._host()._set_selection(index.row())

    def _sync_preview_to_index(self, index: QModelIndex) -> None:
        host = self._host()
        current_hit = host.model.item_at(index.row()) if index.isValid() else None
        host.preview_pane.set_hit(current_hit)
        host.action_bar.set_enabled(index.isValid())
        host.action_bar.set_context(current_hit)
        host._refresh_result_list_accessibility()

    def _refresh_preview(self) -> None:
        self._sync_preview_to_index(self._host().result_list.currentIndex())

    def _handle_query_chip_keypress(self, button: SecondaryButton, event: QKeyEvent) -> bool:
        host = self._host()
        row = self._row_for_chip_button(button)
        if row is None:
            return False
        if event.key() == Qt.Key.Key_Right:
            next_button = row.next_button(button)
            if next_button is not None:
                next_button.setFocus()
                return True
            return False
        if event.key() == Qt.Key.Key_Left:
            previous_button = row.previous_button(button)
            if previous_button is not None:
                previous_button.setFocus()
                return True
            return False
        if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
            host.query_field.setFocus()
            return True
        return False

    def _query_chip_rows(self) -> list[QueryChipRow]:
        host = self._host()
        return [row for row in (host.pinned_queries_row, host.recent_queries_row) if row.isVisible() and row.buttons]

    def _query_chip_buttons(self) -> list[SecondaryButton]:
        buttons: list[SecondaryButton] = []
        for row in self._query_chip_rows():
            buttons.extend(row.buttons)
        return buttons

    def _install_query_chip_filters(self) -> None:
        for button in self._query_chip_buttons():
            button.installEventFilter(cast(Any, self))

    def _focus_first_query_chip(self) -> bool:
        rows = self._query_chip_rows()
        return rows[0].focus_first_button() if rows else False

    def _focus_last_query_chip(self) -> bool:
        rows = self._query_chip_rows()
        return rows[-1].focus_last_button() if rows else False

    def _row_for_chip_button(self, button: SecondaryButton) -> QueryChipRow | None:
        for row in self._query_chip_rows():
            if button in row.buttons:
                return row
        return None

    def _navigate_recent_queries(self, direction: int) -> None:
        host = self._host()
        if not host._recent_queries:
            return
        if direction < 0:
            if host._history_index is None:
                host._history_draft = host.query_field.text()
                next_index = 0
            else:
                next_index = min(host._history_index + 1, len(host._recent_queries) - 1)
        else:
            if host._history_index is None:
                return
            if host._history_index == 0:
                host._history_index = None
                self._set_query_from_history(host._history_draft)
                host._history_draft = ""
                return
            next_index = host._history_index - 1
        host._history_index = next_index
        self._set_query_from_history(host._recent_queries[next_index])

    def _set_query_from_history(self, query: str) -> None:
        host = self._host()
        host._applying_history_query = True
        try:
            host._skip_remember_query = True
            host.query_field.setFocus()
            host.query_field.setText(query)
            host.query_field.setCursorPosition(len(query))
        finally:
            host._applying_history_query = False
