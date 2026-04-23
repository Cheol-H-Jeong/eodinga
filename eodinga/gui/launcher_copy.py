from __future__ import annotations

_EMPTY_QUERY_SUGGESTIONS = (
    "ext:pdf",
    "date:this-week",
    "size:>10M",
    'content:"release notes"',
)

_ACTIVE_QUERY_SUGGESTIONS = (
    "ext:pdf",
    "date:this-week",
    "size:>10M",
    "path:docs",
)


def suggested_filter_queries(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return list(_EMPTY_QUERY_SUGGESTIONS)
    return [token for token in _ACTIVE_QUERY_SUGGESTIONS if token not in normalized]


def append_query_token(query: str, token: str) -> str:
    normalized = query.strip()
    if not normalized:
        return token
    if token in normalized:
        return normalized
    return f"{normalized} {token}"


def empty_state_body(*, query: str, recent_queries: list[str], pinned_queries: list[str]) -> tuple[str, str]:
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        return (
            "Type to search",
            f"Recent: {recent}.{pinned} Click a launcher chip or a filter suggestion, or press Alt+Up to recall recent queries, Alt+1 through Alt+9 to open a top hit, Tab to move to results, Enter to open the top hit, and Ctrl+Enter to reveal its folder.",
        )
    return (
        f'No results for "{query}"',
        "Try another term or click a filter suggestion like ext:pdf, date:this-week, or size:>10M. Press Tab to jump back to the filter or Esc to hide the launcher.",
    )


def shortcut_hint(*, query: str, has_results: bool, result_list_has_focus: bool) -> str:
    if not has_results:
        if query:
            return "Refine with the filter chips or use ext:, date:, size:, or content:. Alt+Up recalls recent queries."
        return "Type a filename, path, or content term, or click a filter chip to start. Alt+Up recalls recent queries."
    if result_list_has_focus:
        return "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
    return "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. Alt+Up recalls recent queries."
