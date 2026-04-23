from __future__ import annotations

from pathlib import Path

from eodinga.common import IndexingStatus, QueryResult, SearchHit


def default_search(query: str, limit: int) -> QueryResult:
    hit = SearchHit(
        path=Path("/tmp/example.txt"),
        parent_path=Path("/tmp"),
        name="example.txt",
        ext="txt",
        highlighted_name="example.txt",
        highlighted_path="/tmp/example.txt",
    )
    items = [hit] if query else []
    return QueryResult(items=items[:limit], total=len(items), elapsed_ms=2.0)


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


def format_indexing_footer(status: IndexingStatus) -> str:
    if status.phase != "indexing":
        return "0 results · 0.0 ms"
    total = str(status.total_files) if status.total_files > 0 else "?"
    parts = [f"{status.processed_files}/{total} files"]
    if status.total_files > 0:
        percent = round((status.processed_files / status.total_files) * 100)
        parts.append(f"{percent}% indexed")
    else:
        parts.append("indexing")
    return " · ".join(parts)
