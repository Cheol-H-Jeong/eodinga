from __future__ import annotations

from eodinga.common import IndexingStatus, SearchHit


def build_empty_state_content(
    *,
    query: str,
    recent_queries: list[str],
    pinned_queries: list[str],
    indexing_details: str,
) -> tuple[str, str, str]:
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        return (
            "Type to search",
            (
                f"Recent: {recent}.{pinned} Click a launcher chip or press Alt+Up and Alt+Down to browse recent "
                "queries, Alt+1 through Alt+9 to open a top hit, Tab to move to results, Enter to open the top "
                "hit, and Ctrl+Enter to reveal its folder."
            ),
            indexing_details,
        )
    return (
        f'No results for "{query}"',
        (
            "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. Press Alt+Up "
            "and Alt+Down to revisit recent queries, Tab to jump back to the filter, or Esc to hide the launcher."
        ),
        indexing_details,
    )


def build_shortcut_hint(*, has_results: bool, has_query: bool, result_list_has_focus: bool) -> str:
    if not has_results:
        if has_query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up and Alt+Down browse recent queries."
        return "Type a filename, path, or content term. Alt+Up and Alt+Down browse recent queries."
    if result_list_has_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. "
            "Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. Shift+Enter "
        "shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. Alt+Up and Alt+Down browse "
        "recent queries."
    )


def build_result_list_accessible_description(
    *,
    count: int,
    current_name: str | None,
    current_row: int | None,
) -> str:
    description = f"{count} launcher results."
    if current_name is not None and current_row is not None:
        description = f"{description} Selected {current_row} of {count}: {current_name}."
    return f"{description} Use Up and Down to move between results, Enter to open, and Alt+1 through Alt+9 for quick picks."


def build_status_footer(
    *,
    query: str,
    indexing_status: IndexingStatus,
    total_results: int,
    elapsed_ms: float,
) -> tuple[str, str]:
    if not query:
        if indexing_status.phase == "indexing":
            total = str(indexing_status.total_files) if indexing_status.total_files > 0 else "?"
            parts = [f"{indexing_status.processed_files}/{total} files"]
            if indexing_status.total_files > 0:
                percent = round((indexing_status.processed_files / indexing_status.total_files) * 100)
                parts.append(f"{percent}% indexed")
            else:
                parts.append("indexing")
            return ("Indexing", " · ".join(parts))
        return ("Idle", "0 results · 0.0 ms")
    status = "Ready" if total_results > 0 else "No results"
    return (status, f"{total_results} results · {elapsed_ms:.1f} ms")


def find_restore_selection_row(items: list[SearchHit], previous_hit: SearchHit | None) -> int | None:
    if previous_hit is None:
        return None
    for row, item in enumerate(items):
        if item.path == previous_hit.path:
            return row
    return None
