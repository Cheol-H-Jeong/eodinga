from __future__ import annotations

from functools import lru_cache

STATEMENT_CACHE_SIZE = 128
CONTENT_TEXT_BATCH_SIZE = 128


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_record_batch_sql(where_sql: str) -> str:
    sql = "SELECT files.* FROM files"
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY files.name_lower ASC, files.path ASC, files.id ASC LIMIT ? OFFSET ?"
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_path_candidates_fts_sql(
    path_match_sql: str,
    where_sql: str,
    case_sensitive: bool,
) -> str:
    sql = """
        SELECT files.*
        FROM paths_fts
        JOIN files ON files.id = paths_fts.rowid
    """
    filters: list[str] = []
    if path_match_sql:
        filters.append(path_match_sql)
    if where_sql:
        filters.append(where_sql)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if case_sensitive else "files.name_lower LIKE ?"
    sql += (
        f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END,"
        f" bm25(paths_fts, 8.0, 2.0, 1.0) ASC, {order_expr} ASC, files.path ASC, files.id ASC LIMIT ?"
    )
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_path_candidates_scan_sql(
    positive_term_count: int,
    where_sql: str,
    case_sensitive: bool,
) -> str:
    sql = "SELECT files.* FROM files"
    filters: list[str] = []
    for _ in range(positive_term_count):
        if case_sensitive:
            filters.append("(instr(files.name, ?) > 0 OR instr(files.path, ?) > 0)")
        else:
            filters.append("(instr(lower(files.name), ?) > 0 OR instr(lower(files.path), ?) > 0)")
    if where_sql:
        filters.append(where_sql)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if case_sensitive else "files.name_lower LIKE ?"
    sql += (
        f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END,"
        f" {order_expr} ASC, files.path ASC, files.id ASC LIMIT ?"
    )
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_content_candidates_sql(content_match_sql: str, where_sql: str) -> str:
    sql = f"""
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
        WHERE {content_match_sql}
    """
    if where_sql:
        sql += f" AND {where_sql}"
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC, files.name_lower ASC, files.path ASC, files.id ASC LIMIT ?"
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_auto_content_candidates_sql(where_sql: str) -> str:
    sql = """
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
        WHERE content_fts MATCH ?
    """
    if where_sql:
        sql += f" AND {where_sql}"
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC, files.name_lower ASC, files.path ASC, files.id ASC LIMIT ?"
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_content_backfill_sql(where_sql: str) -> str:
    sql = """
        SELECT files.*
        FROM files
        JOIN content_map ON content_map.file_id = files.id
    """
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY files.name_lower ASC, files.path ASC, files.id ASC LIMIT ? OFFSET ?"
    return sql


@lru_cache(maxsize=STATEMENT_CACHE_SIZE)
def render_content_texts_sql(chunk_size: int) -> str:
    placeholders = ", ".join("?" for _ in range(chunk_size))
    return f"""
        SELECT content_map.file_id, content_fts.title, content_fts.head_text, content_fts.body_text
        FROM content_map
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        WHERE content_map.file_id IN ({placeholders})
    """
