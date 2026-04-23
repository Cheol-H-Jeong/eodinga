from __future__ import annotations


def build_empty_state_body(recent_queries: list[str], pinned_queries: list[str]) -> str:
    recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
    pinned = ", ".join(pinned_queries[:3]) if pinned_queries else "No pinned queries yet."
    return (
        f"Recent: {recent} Pinned: {pinned} "
        "Press Alt+Up to recall recent queries, click a pinned chip to apply it, "
        "Alt+1 through Alt+9 to open a top hit, Tab to move to results, "
        "Enter to open the top hit, and Ctrl+Enter to reveal its folder."
    )


def build_shortcut_hint(*, has_results: bool, results_focused: bool, query: str, has_active_filters: bool, has_pins: bool) -> str:
    if not has_results:
        if query:
            if has_active_filters:
                return "Active filters stay visible above results. Alt+Up recalls recent queries."
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries."
        if has_pins:
            return "Type a filename, path, or content term. Click a pinned chip or press Alt+Up for recents."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries."
    if results_focused:
        return (
            "Enter opens. Alt+1..9 quick-picks. Up/Down wraps. "
            "Home/End and PgUp/PgDn jump. Ctrl+Enter reveals. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. "
        "Enter opens the top hit. Alt+1..9 quick-picks. Alt+Up recalls recent queries."
    )


def format_query_status(total: int, elapsed_ms: float, active_filter_count: int) -> str:
    status = f"{total} results · {elapsed_ms:.1f} ms"
    if active_filter_count > 0:
        suffix = "filter" if active_filter_count == 1 else "filters"
        return f"{status} · {active_filter_count} {suffix}"
    return status
