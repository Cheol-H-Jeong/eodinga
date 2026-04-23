from __future__ import annotations

from eodinga.common import IndexingStatus
from eodinga.gui.launcher_state import format_indexing_status


def launcher_empty_state_content(
    *,
    query: str,
    recent_queries: list[str],
    pinned_queries: list[str],
    indexing_status: IndexingStatus,
) -> tuple[str, str, str]:
    details = format_indexing_status(indexing_status)
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        body = (
            f"Recent: {recent}.{pinned} Click a launcher chip or press Alt+Up and Alt+Down to browse recent queries, "
            "Alt+1 through Alt+9 to open a top hit, Tab to move to results, Enter to open the top hit, and Ctrl+Enter "
            "to reveal its folder."
        )
        return "Type to search", body, details
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. Press Alt+Up and "
        "Alt+Down to revisit recent queries, Tab to jump back to the filter, or Esc to hide the launcher."
    )
    return f'No results for "{query}"', body, details


def launcher_shortcut_hint(*, has_results: bool, has_query: bool, results_have_focus: bool) -> str:
    if not has_results:
        if has_query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up and Alt+Down browse recent queries."
        return "Type a filename, path, or content term. Alt+Up and Alt+Down browse recent queries."
    if results_have_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. "
            "Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. Shift+Enter "
        "shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. Alt+Up and Alt+Down browse recent queries."
    )


def launcher_result_list_accessibility(*, count: int, current_name: str | None, current_row: int) -> str:
    if count == 0:
        return "No launcher results are available."
    description = f"{count} launcher results."
    if current_name is not None:
        description = f"{description} Selected {current_row} of {count}: {current_name}."
    return f"{description} Use Up and Down to move between results, Enter to open, and Alt+1 through Alt+9 for quick picks."


__all__ = ["launcher_empty_state_content", "launcher_result_list_accessibility", "launcher_shortcut_hint"]
