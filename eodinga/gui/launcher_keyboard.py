from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit

_EMPTY_QUERY_HINT = "Type a filename, path, or content term. Alt+Up and Alt+Down browse recent queries."
_EMPTY_RESULTS_HINT = "Refine with ext:, date:, size:, or content: filters. Alt+Up and Alt+Down browse recent queries."
_RESULTS_FOCUSED_HINT = (
    "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. "
    "Alt+N copies name. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. "
    "Ctrl+A or Ctrl+L returns to filter."
)
_QUERY_FOCUSED_HINT = (
    "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. "
    "Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. "
    "Alt+Up and Alt+Down browse recent queries."
)
_CHIP_FOCUSED_HINT = (
    "Enter applies the highlighted query chip. Left/Right move across chips. "
    "Tab and Shift+Tab move into chip groups from the search field."
)


def build_empty_state_body(recent_queries: list[str], pinned_queries: list[str]) -> str:
    recent_text = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
    pinned_text = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
    return (
        f"Recent: {recent_text}.{pinned_text} Click a launcher chip or press Alt+Up and Alt+Down to browse "
        "recent queries, Alt+1 through Alt+9 to open a top hit, Tab to move to results, Enter to open the top "
        "hit, and Ctrl+Enter to reveal its folder."
    )


def build_no_results_body() -> str:
    return (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Alt+Up and Alt+Down to revisit recent queries, Tab to jump back to the filter, "
        "or Esc to hide the launcher."
    )


def build_shortcut_hint(*, has_query: bool, has_results: bool, results_focused: bool, chip_focused: bool) -> str:
    if chip_focused:
        return _CHIP_FOCUSED_HINT
    if not has_results:
        return _EMPTY_RESULTS_HINT if has_query else _EMPTY_QUERY_HINT
    if results_focused:
        return _RESULTS_FOCUSED_HINT
    return _QUERY_FOCUSED_HINT


def build_results_accessible_description(*, count: int, current_name: str | None, current_row: int | None) -> str:
    if count == 0:
        return "No launcher results are available."
    description = f"{count} launcher results."
    if current_name is not None and current_row is not None:
        description = f"{description} Selected {current_row} of {count}: {current_name}."
    return (
        f"{description} Use Up and Down to move between results, Enter to open, and Alt+1 through Alt+9 "
        "for quick picks."
    )


def build_search_field_accessibility(*, filters: list[str], has_query_chips: bool) -> str:
    description = "Type a filename, path, or content term to search the index."
    if filters:
        return f"{description} Active filters: {', '.join(filters)}."
    if has_query_chips:
        return f"{description} Press Tab or Shift+Tab to focus launcher query chips."
    return description


def should_edit_query_from_results(event: QKeyEvent) -> bool:
    modifiers = event.modifiers()
    if modifiers not in {Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier}:
        return False
    if event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
        return True
    return bool(event.text())


def forward_keypress_to_line_edit(line_edit: QLineEdit, event: QKeyEvent) -> None:
    line_edit.setFocus()
    line_edit.setCursorPosition(len(line_edit.text()))
    forwarded = QKeyEvent(
        QEvent.Type.KeyPress,
        event.key(),
        event.modifiers(),
        event.text(),
        event.isAutoRepeat(),
        event.count(),
    )
    QApplication.sendEvent(line_edit, forwarded)
