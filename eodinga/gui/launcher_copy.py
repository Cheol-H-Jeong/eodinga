from __future__ import annotations

from eodinga.common import IndexingStatus


def build_empty_state_content(
    *,
    query: str,
    has_results: bool,
    recent_queries: list[str],
    pinned_queries: list[str],
    indexing_details: str,
) -> tuple[str, str, str]:
    if has_results:
        return "", "", indexing_details
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        body = (
            f"Recent: {recent}.{pinned} Click a launcher chip or press Alt+Up to recall recent queries, "
            "Alt+1 through Alt+9 to open a top hit, Tab to move to results, Enter to open the top hit, "
            "and Ctrl+Enter to reveal its folder."
        )
        return "Type to search", body, indexing_details
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Tab to jump back to the filter or Esc to hide the launcher."
    )
    return f'No results for "{query}"', body, indexing_details


def build_shortcut_hint(*, has_results: bool, query: str, results_have_focus: bool) -> str:
    if not has_results:
        if query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries."
    if results_have_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. "
            "Alt+N copies name. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. "
            "Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. "
        "Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. "
        "Alt+Up recalls recent queries."
    )


def build_status_footer(*, query: str, total: int, elapsed_ms: float, indexing_status: IndexingStatus) -> tuple[str, str]:
    if not query:
        if indexing_status.phase == "indexing":
            total_files = str(indexing_status.total_files) if indexing_status.total_files > 0 else "?"
            parts = [f"{indexing_status.processed_files}/{total_files} files"]
            if indexing_status.total_files > 0:
                percent = round((indexing_status.processed_files / indexing_status.total_files) * 100)
                parts.append(f"{percent}% indexed")
            else:
                parts.append("indexing")
            return "Indexing", " · ".join(parts)
        return "Idle", "0 results · 0.0 ms"
    return ("Ready" if total > 0 else "No results"), f"{total} results · {elapsed_ms:.1f} ms"
