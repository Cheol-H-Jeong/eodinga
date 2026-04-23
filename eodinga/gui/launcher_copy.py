from __future__ import annotations

from eodinga.common import SearchHit


def empty_state_content(
    query: str,
    *,
    recent_queries: list[str],
    pinned_queries: list[str],
) -> tuple[str, str]:
    if not query:
        recent_summary = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned_summary = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        body = (
            f"Recent: {recent_summary}.{pinned_summary} Click a launcher chip or press Alt+Up and Alt+Down "
            "to browse recent queries, Alt+1 through Alt+9 to open a top hit, Tab to move to results, "
            "Enter to open the top hit, and Ctrl+Enter to reveal its folder."
        )
        return "Type to search", body
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Alt+Up and Alt+Down to revisit recent queries, Tab to jump back to the filter, "
        "or Esc to hide the launcher."
    )
    return f'No results for "{query}"', body


def shortcut_hint(query: str, *, has_results: bool, result_list_has_focus: bool) -> str:
    if not has_results:
        if query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up and Alt+Down browse recent queries."
        return "Type a filename, path, or content term. Alt+Up and Alt+Down browse recent queries."
    if result_list_has_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. "
            "Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. "
        "Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. "
        "Alt+Up and Alt+Down browse recent queries."
    )


def result_list_accessibility(*, count: int, current_row: int | None, current_hit: SearchHit | None) -> str:
    if count == 0:
        return "No launcher results are available."
    description = f"{count} launcher results."
    if current_hit is not None and current_row is not None:
        description = f"{description} Selected {current_row} of {count}: {current_hit.name}."
    return (
        f"{description} Use Up and Down to move between results, Enter to open, and Alt+1 through Alt+9 for quick picks."
    )
