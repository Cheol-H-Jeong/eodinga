from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QWidget


def apply_tab_order(widgets: Sequence[QWidget]) -> None:
    for current, following in zip(widgets, widgets[1:], strict=False):
        QWidget.setTabOrder(current, following)


def focus_first_available(widgets: Sequence[QWidget | None]) -> bool:
    for widget in widgets:
        if widget is not None:
            widget.setFocus()
            return True
    return False


def focus_last_available(widgets: Sequence[QWidget | None]) -> bool:
    for widget in reversed(widgets):
        if widget is not None:
            widget.setFocus()
            return True
    return False


def launcher_tab_order(
    query_field: QWidget,
    pinned_buttons: Sequence[QWidget],
    recent_buttons: Sequence[QWidget],
    result_list: QWidget,
    action_buttons: Sequence[QWidget],
) -> None:
    apply_tab_order([query_field, *pinned_buttons, *recent_buttons, result_list, *action_buttons])
