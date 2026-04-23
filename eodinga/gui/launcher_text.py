from __future__ import annotations

from eodinga.common import IndexingStatus
from eodinga.gui.launcher_state import format_indexing_status


def empty_state_content(query: str, recent_queries: list[str], indexing_status: IndexingStatus) -> tuple[str, str, str]:
    details = format_indexing_status(indexing_status)
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        return (
            "Type to search",
            (
                f"Recent: {recent} Press Alt+Up to recall recent queries, Alt+1 through Alt+9 to open a top hit, "
                "Tab to move to results, Enter to open the top hit, and Ctrl+Enter to reveal its folder."
            ),
            details,
        )
    return (
        f'No results for "{query}"',
        (
            "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
            "Press Tab to jump back to the filter or Esc to hide the launcher."
        ),
        details,
    )


def shortcut_hint(*, has_results: bool, has_query: bool, results_has_focus: bool) -> str:
    if not has_results:
        if has_query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries."
    if results_has_focus:
        return (
            "Enter opens. Alt+1..9 quick-picks. Up/Down wraps. "
            "Home/End and PgUp/PgDn jump. Ctrl+Enter reveals. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. "
        "Enter opens the top hit. Alt+1..9 quick-picks. Alt+Up recalls recent queries."
    )
