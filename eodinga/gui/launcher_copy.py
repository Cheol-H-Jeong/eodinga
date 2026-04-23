from __future__ import annotations

from eodinga.common import IndexingStatus


def build_empty_state_content(
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
            f"Recent: {recent}.{pinned} Press Alt+Up to recall recent queries, Alt+1 through Alt+9 to open a top hit, "
            "Tab to move to results, Enter to open the top hit, and Ctrl+Enter to reveal its folder."
        )
        return "Type to search", body, details
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Tab to jump back to the filter or Esc to hide the launcher."
    )
    return f'No results for "{query}"', body, details


def build_shortcut_hint(*, has_results: bool, query: str, result_list_has_focus: bool) -> str:
    if not has_results:
        if query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up recalls recent queries."
        return "Type a filename, path, or content term. Alt+Up recalls recent queries."
    if result_list_has_focus:
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


def format_indexing_status(status: IndexingStatus) -> str:
    if status.phase != "indexing":
        return "Indexing idle. Results update automatically when your roots change."
    total = str(status.total_files) if status.total_files > 0 else "?"
    progress = ""
    if status.total_files > 0:
        percent = round((status.processed_files / status.total_files) * 100)
        progress = f" ({percent}%)"
    root_label = f" in {status.current_root}" if status.current_root is not None else ""
    return f"Indexing {status.processed_files}/{total} files{progress}{root_label}."
