from __future__ import annotations


def build_empty_state_body(*, query: str, recent_queries: list[str], pinned_queries: list[str]) -> str:
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        return (
            f"Recent: {recent}.{pinned} Click a launcher chip or press Alt+Up to recall recent queries, "
            "Alt+P to pin the current query, Alt+1 through Alt+9 to open a top hit, Tab to move to results, "
            "Enter to open the top hit, and Ctrl+Enter to reveal its folder."
        )
    return (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Alt+P to pin the current query, Tab to jump back to the filter, or Esc to hide the launcher."
    )


def build_shortcut_hint(*, has_results: bool, query_present: bool, result_list_focused: bool) -> str:
    if not has_results:
        if query_present:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries. Alt+P pins the current query."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries. Alt+P pins the current query."
    if result_list_focused:
        return "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. Alt+P pins the current query. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
    return "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+P pins the current query. Alt+1..9 quick-picks. Alt+Up recalls recent queries."
