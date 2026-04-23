from __future__ import annotations

from eodinga.common import IndexingStatus

from .launcher_state import format_indexing_status


def empty_state_content(
    query: str,
    *,
    recent_queries: list[str],
    pinned_queries: list[str],
    indexing_status: IndexingStatus,
) -> tuple[str, str, str]:
    details = format_indexing_status(indexing_status)
    if not query:
        recent_text = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned_text = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        body = (
            f"Recent: {recent_text}.{pinned_text} Click a launcher chip or press Alt+Up and Alt+Down to browse recent "
            "queries, Alt+P to pin the current query, Alt+1 through Alt+9 to open a top hit, Tab to move to results, "
            "Enter to open the top hit, and Ctrl+Enter to reveal its folder."
        )
        return ("Type to search", body, details)
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Alt+P to pin this query, Alt+Up and Alt+Down to revisit recent queries, "
        "Tab to jump back to the filter, or Esc to hide the launcher."
    )
    return (f'No results for "{query}"', body, details)


def shortcut_hint(*, has_results: bool, has_query: bool, result_list_has_focus: bool) -> str:
    if not has_results:
        if has_query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+P pins the current query. Alt+Up and Alt+Down browse recent queries."
        return "Type a filename, path, or content term. Alt+P pins the current query. Alt+Up and Alt+Down browse recent queries."
    if result_list_has_focus:
        return "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. Alt+P pins the current query. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
    return "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+P pins the current query. Alt+1..9 quick-picks. Alt+Up and Alt+Down browse recent queries."
