from __future__ import annotations


def format_empty_state_body(*, recent_summary: str, pinned_summary: str | None, has_recent_queries: bool) -> str:
    sections = [f"Recent: {recent_summary}."]
    if pinned_summary:
        sections.append(f"Pinned: {pinned_summary}.")
    guidance: list[str] = []
    if pinned_summary:
        guidance.append("Press Tab to reach pinned queries")
    guidance.append("Type a filename, path, or content term to search")
    if has_recent_queries:
        guidance.append("or press Alt+Up and Alt+Down to revisit recent queries")
    return " ".join(sections + [f"{', '.join(guidance)}."])


def format_no_results_body(*, query: str, has_recent_queries: bool) -> str:
    guidance = ["Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M"]
    if has_recent_queries:
        guidance.append("Press Alt+Up and Alt+Down to revisit recent queries")
    guidance.append("Tab jumps back to the filter")
    guidance.append("Esc hides the launcher")
    return f'No results for "{query}"', ". ".join(guidance) + "."


def format_shortcut_hint(
    *,
    has_results: bool,
    query: str,
    result_list_has_focus: bool,
    has_recent_queries: bool,
    has_chip_queries: bool,
) -> str:
    if not has_results:
        if query:
            hint = "Refine with ext:, date:, size:, or content: filters."
            if has_recent_queries:
                return f"{hint} Alt+Up and Alt+Down browse recent queries."
            return hint
        hint = "Type a filename, path, or content term."
        if has_chip_queries and has_recent_queries:
            return f"{hint} Tab reaches launcher chips. Alt+Up and Alt+Down browse recent queries."
        if has_chip_queries:
            return f"{hint} Tab reaches launcher chips."
        if has_recent_queries:
            return f"{hint} Alt+Up and Alt+Down browse recent queries."
        return hint
    if result_list_has_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. "
            "Alt+N copies name. Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. "
            "Ctrl+A or Ctrl+L returns to filter."
        )
    return (
        "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit. "
        "Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. Alt+1..9 quick-picks. "
        "Alt+Up and Alt+Down browse recent queries."
    )
