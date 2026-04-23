from __future__ import annotations

from PySide6.QtWidgets import QLineEdit


def navigate_launcher_history(
    *,
    recent_queries: list[str],
    direction: int,
    history_index: int | None,
    history_draft: str,
    current_query: str,
) -> tuple[int | None, str, str | None]:
    if not recent_queries:
        return history_index, history_draft, None
    if direction < 0:
        if history_index is None:
            return 0, current_query, recent_queries[0]
        next_index = min(history_index + 1, len(recent_queries) - 1)
        return next_index, history_draft, recent_queries[next_index]
    if history_index is None:
        return None, history_draft, None
    if history_index == 0:
        return None, "", history_draft
    next_index = history_index - 1
    return next_index, history_draft, recent_queries[next_index]


def apply_launcher_history_query(query_field: QLineEdit, query: str) -> None:
    query_field.setFocus()
    query_field.setText(query)
    query_field.setCursorPosition(len(query))


__all__ = ["apply_launcher_history_query", "navigate_launcher_history"]
