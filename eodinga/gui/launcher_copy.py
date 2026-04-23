from __future__ import annotations


def empty_state_text(query: str, recent_queries: list[str], pinned_queries: list[str]) -> tuple[str, str]:
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        return (
            "Type to search",
            "Recent: "
            f"{recent}.{pinned} Click a launcher chip or press Alt+Up and Alt+Down to browse recent queries, "
            "Tab through chips, results, and actions, Alt+1 through Alt+9 to open a top hit, Enter to open the "
            "top hit, and Ctrl+Enter to reveal its folder.",
        )
    return (
        f'No results for "{query}"',
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M. "
        "Press Alt+Up and Alt+Down to revisit recent queries, Tab to cycle through launcher controls, "
        "or Esc to hide the launcher.",
    )


def shortcut_hint(*, has_results: bool, query: str, result_list_has_focus: bool, action_has_focus: bool) -> str:
    if not has_results:
        if query:
            return "Refine with ext:, date:, size:, or content: filters. Alt+Up and Alt+Down browse recent queries."
        return "Type a filename, path, or content term. Alt+Up and Alt+Down browse recent queries."
    if result_list_has_focus:
        return (
            "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name. "
            "Alt+1..9 quick-picks. Up/Down wraps. Home/End and PgUp/PgDn jump. Tab moves to actions. Shift+Tab "
            "returns to chips or the filter. Ctrl+A or Ctrl+L returns to filter."
        )
    if action_has_focus:
        return (
            "Enter activates the focused action. Tab moves across actions. Shift+Tab returns to results. Ctrl+L "
            "or Ctrl+A jumps back to the filter. Alt+1..9 quick-picks still open top hits."
        )
    return (
        "Tab moves through chips, results, and actions. Down/Up navigate results. Home/End and PgUp/PgDn jump. "
        "Enter opens the top hit. Shift+Enter shows properties. Alt+C copies path. Alt+N copies name. "
        "Alt+1..9 quick-picks. Alt+Up and Alt+Down browse recent queries."
    )


def result_list_accessibility(*, count: int, current_name: str | None, current_row: int | None) -> str:
    if count == 0:
        return "No launcher results are available."
    description = f"{count} launcher results."
    if current_name is not None and current_row is not None:
        description = f"{description} Selected {current_row} of {count}: {current_name}."
    return (
        f"{description} Use Up and Down to move between results, Enter to open, Alt+1 through Alt+9 for quick picks, "
        "and Tab to move into the action bar."
    )
