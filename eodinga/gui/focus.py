from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import QListView, QWidget


def focus_chain(
    *,
    chip_buttons: Iterable[QWidget],
    result_list: QListView,
    action_buttons: Iterable[QWidget],
) -> list[QWidget]:
    chain = [button for button in chip_buttons if button.isVisible() and button.isEnabled()]
    if result_list.isVisible():
        chain.append(result_list)
    chain.extend(button for button in action_buttons if button.isVisible() and button.isEnabled())
    return chain


def configure_tab_loop(query_field: QWidget, chain: Iterable[QWidget]) -> None:
    widgets = list(chain)
    previous = query_field
    for widget in widgets:
        QWidget.setTabOrder(previous, widget)
        previous = widget
    if widgets:
        QWidget.setTabOrder(previous, query_field)
