from __future__ import annotations


def format_history_guidance(*, has_history: bool) -> str:
    if has_history:
        return " Alt+Up and Alt+Down browse recent queries."
    return ""


def format_history_action(*, has_history: bool) -> str:
    if has_history:
        return " Press Alt+Up and Alt+Down to browse recent queries."
    return ""


def format_quick_pick_range(count: int) -> str:
    quick_pick_count = min(max(count, 0), 9)
    if quick_pick_count <= 0:
        return ""
    if quick_pick_count == 1:
        return "Alt+1"
    return f"Alt+1 through Alt+{quick_pick_count}"


def format_quick_pick_action(count: int, *, noun: str) -> str:
    quick_pick_range = format_quick_pick_range(count)
    if not quick_pick_range:
        return ""
    return f" {quick_pick_range} {noun}."


def build_empty_state_body(
    *,
    query: str,
    recent_queries: list[str],
    pinned_queries: list[str],
    visible_results: int,
) -> tuple[str, str]:
    has_history = bool(recent_queries)
    if not query:
        recent = ", ".join(recent_queries[:3]) if recent_queries else "No recent queries yet."
        pinned = f" Pinned: {', '.join(pinned_queries[:3])}." if pinned_queries else ""
        body = (
            f"Recent: {recent}.{pinned} Click a launcher chip"
            f"{format_history_action(has_history=has_history)}"
            f"{format_quick_pick_action(visible_results, noun='open a top hit')} Tab moves to results."
            " Enter opens the top hit. Ctrl+Enter reveals its folder."
        )
        return "Type to search", body
    body = (
        "Try another term or refine with filters like ext:pdf, date:this-week, and size:>10M."
        f"{format_history_action(has_history=has_history)} Tab jumps back to the filter. Esc hides the launcher."
    )
    return f'No results for "{query}"', body


def build_shortcut_hint(
    *,
    has_results: bool,
    has_query: bool,
    result_list_focused: bool,
    has_history: bool,
    visible_results: int,
) -> str:
    if not has_results:
        prefix = "Refine with ext:, date:, size:, or content: filters." if has_query else "Type a filename, path, or content term."
        return prefix + format_history_guidance(has_history=has_history)
    quick_picks = format_quick_pick_range(visible_results)
    if result_list_focused:
        hint = "Enter opens. Shift+Enter shows properties. Ctrl+Enter reveals. Alt+C copies path. Alt+N copies name."
    else:
        hint = (
            "Tab moves to results. Down/Up navigate. Home/End and PgUp/PgDn jump. Enter opens the top hit."
            " Shift+Enter shows properties. Alt+C copies path. Alt+N copies name."
        )
    if quick_picks:
        hint += f" {quick_picks} quick-picks."
    if result_list_focused:
        return hint + " Up/Down wraps. Home/End and PgUp/PgDn jump. Ctrl+A or Ctrl+L returns to filter."
    return hint + format_history_guidance(has_history=has_history)


def build_result_list_accessible_description(*, count: int, current_row: int, current_name: str | None) -> str:
    if count <= 0:
        return "No launcher results are available."
    description = f"{count} launcher results."
    if current_name is not None:
        description = f"{description} Selected {current_row} of {count}: {current_name}."
    return f"{description} Use Up and Down to move between results, Enter to open, and {format_quick_pick_range(count)} for quick picks."
