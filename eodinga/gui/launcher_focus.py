from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from PySide6.QtWidgets import QWidget


def ordered_focus_targets(*groups: Iterable[QWidget]) -> list[QWidget]:
    targets: list[QWidget] = []
    for group in groups:
        for widget in group:
            if _is_focus_target(widget):
                targets.append(widget)
    return targets


def cycle_focus(current: QWidget, targets: list[QWidget], *, backwards: bool = False) -> QWidget | None:
    if not targets:
        return None
    if current not in targets:
        return targets[-1] if backwards else targets[0]
    current_index = targets.index(current)
    step = -1 if backwards else 1
    return targets[(current_index + step) % len(targets)]


def _is_focus_target(widget: QWidget) -> bool:
    return widget.isVisible() and widget.isEnabled() and widget.focusPolicy() != widget.focusPolicy().NoFocus


class LauncherFocusController:
    def __init__(
        self,
        *,
        query_field: QWidget,
        pinned_buttons,
        recent_buttons,
        result_list: QWidget,
        action_buttons,
        has_results,
        ensure_result_selection,
    ) -> None:
        self._query_field = query_field
        self._pinned_buttons = pinned_buttons
        self._recent_buttons = recent_buttons
        self._result_list = result_list
        self._action_buttons = action_buttons
        self._has_results = has_results
        self._ensure_result_selection = ensure_result_selection

    def install_event_filters(self, event_filter: QWidget) -> None:
        for widget in self.all_widgets():
            widget.installEventFilter(event_filter)

    def focus_widgets(self) -> tuple[QWidget, ...]:
        return tuple(self.focus_targets())

    def all_widgets(self) -> tuple[QWidget, ...]:
        return tuple(
            [self._query_field, *self._pinned_buttons(), *self._recent_buttons(), self._result_list, *self._action_buttons()]
        )

    def is_chip_button(self, watched: object) -> bool:
        return watched in self._chip_buttons()

    def focus_relative_to(self, current: QWidget, *, backwards: bool) -> bool:
        target = cycle_focus(current, self.focus_targets(), backwards=backwards)
        if target is None:
            return False
        target.setFocus()
        if target is self._result_list:
            self._ensure_result_selection()
        return True

    def focus_query_backwards(self) -> bool:
        if self._has_results():
            self._result_list.setFocus()
            self._ensure_result_selection()
            return True
        chip_buttons = self._recent_buttons() or self._pinned_buttons()
        if not chip_buttons:
            return False
        chip_buttons[-1].setFocus()
        return True

    def focus_targets(self) -> list[QWidget]:
        groups: list[list[QWidget]] = [[self._query_field], self._pinned_buttons(), self._recent_buttons()]
        if self._has_results():
            groups.append([self._result_list])
        groups.append(self._action_buttons())
        return ordered_focus_targets(*groups)

    def _chip_buttons(self) -> list[QWidget]:
        return cast(list[QWidget], self._pinned_buttons() + self._recent_buttons())
