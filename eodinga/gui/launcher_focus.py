from __future__ import annotations

from typing import cast

from PySide6.QtCore import QModelIndex, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QListView, QWidget

from eodinga.gui.widgets.query_chip_row import QueryChipRow


def focusable_query_buttons(*rows: QueryChipRow) -> list[QWidget]:
    buttons: list[QWidget] = []
    for row in rows:
        if row.isVisible():
            buttons.extend(row.buttons)
    return buttons


def install_chip_event_filters(host: QObject, *rows: QueryChipRow) -> None:
    for button in focusable_query_buttons(*rows):
        button.installEventFilter(host)


def rebuild_tab_order(query_field: QWidget, result_list: QWidget, *rows: QueryChipRow) -> None:
    focus_chain: list[QWidget] = [query_field, *focusable_query_buttons(*rows), result_list]
    for current, following in zip(focus_chain, focus_chain[1:]):
        QWidget.setTabOrder(current, following)


def select_filter_text(query_field: QLineEdit, query: str) -> None:
    query_field.setFocus()
    query_text = query_field.text()
    start = query_text.find(query)
    if start < 0:
        query_field.selectAll()
        return
    query_field.setSelection(start, len(query))


def handle_chip_keypress(
    button: QWidget,
    event: QKeyEvent,
    *,
    query_field: QWidget,
    result_list: QListView,
    model,
    rows: tuple[QueryChipRow, ...],
) -> bool:
    buttons = focusable_query_buttons(*rows)
    if event.key() not in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab} or button not in buttons:
        return False
    index = buttons.index(button)
    if event.key() == Qt.Key.Key_Backtab:
        if index == 0:
            query_field.setFocus(Qt.FocusReason.BacktabFocusReason)
        else:
            buttons[index - 1].setFocus(Qt.FocusReason.BacktabFocusReason)
        return True
    if index == len(buttons) - 1:
        result_list.setFocus(Qt.FocusReason.TabFocusReason)
        if not result_list.currentIndex().isValid() and model.rowCount() > 0:
            result_list.setCurrentIndex(cast(QModelIndex, model.index(0, 0)))
        return True
    buttons[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
    return True


def handle_query_field_keypress(
    event: QKeyEvent,
    *,
    result_list: QListView,
    model,
    rows: tuple[QueryChipRow, ...],
    move_selection,
    page_step: int,
    set_selection,
) -> bool:
    buttons = focusable_query_buttons(*rows)
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab} and buttons:
        if event.key() == Qt.Key.Key_Backtab:
            buttons[-1].setFocus(Qt.FocusReason.BacktabFocusReason)
        else:
            buttons[0].setFocus(Qt.FocusReason.TabFocusReason)
        return True
    if model.rowCount() == 0:
        return False
    if event.key() == Qt.Key.Key_Down:
        result_list.setFocus()
        if not result_list.currentIndex().isValid():
            set_selection(0)
        else:
            move_selection(1)
        return True
    if event.key() == Qt.Key.Key_Up:
        result_list.setFocus()
        if not result_list.currentIndex().isValid():
            set_selection(model.rowCount() - 1)
        else:
            move_selection(-1)
        return True
    if event.key() == Qt.Key.Key_Home:
        result_list.setFocus()
        set_selection(0)
        return True
    if event.key() == Qt.Key.Key_End:
        result_list.setFocus()
        set_selection(model.rowCount() - 1)
        return True
    if event.key() == Qt.Key.Key_PageDown:
        result_list.setFocus()
        move_selection(page_step)
        return True
    if event.key() == Qt.Key.Key_PageUp:
        result_list.setFocus()
        move_selection(-page_step)
        return True
    if event.key() in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
        result_list.setFocus()
        if not result_list.currentIndex().isValid() and model.rowCount() > 0:
            result_list.setCurrentIndex(cast(QModelIndex, model.index(0, 0)))
        return True
    return False


def handle_result_list_keypress(event: QKeyEvent, *, query_field: QWidget, result_list: QListView, rows: tuple[QueryChipRow, ...], move_selection, page_step: int, set_selection) -> bool:
    if event.key() == Qt.Key.Key_Tab:
        query_field.setFocus(Qt.FocusReason.TabFocusReason)
        return True
    if event.key() == Qt.Key.Key_Backtab:
        buttons = focusable_query_buttons(*rows)
        if buttons:
            buttons[-1].setFocus(Qt.FocusReason.BacktabFocusReason)
        else:
            query_field.setFocus(Qt.FocusReason.BacktabFocusReason)
        return True
    if event.key() == Qt.Key.Key_Down:
        move_selection(1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Up:
        move_selection(-1, wrap=True)
        return True
    if event.key() == Qt.Key.Key_Home:
        set_selection(0)
        return True
    if event.key() == Qt.Key.Key_End:
        set_selection(result_list.model().rowCount() - 1)
        return True
    if event.key() == Qt.Key.Key_PageDown:
        move_selection(page_step)
        return True
    if event.key() == Qt.Key.Key_PageUp:
        move_selection(-page_step)
        return True
    return False


__all__ = [
    "focusable_query_buttons",
    "handle_chip_keypress",
    "handle_query_field_keypress",
    "handle_result_list_keypress",
    "install_chip_event_filters",
    "rebuild_tab_order",
    "select_filter_text",
]
