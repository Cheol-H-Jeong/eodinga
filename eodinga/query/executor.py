from __future__ import annotations

import re
import sqlite3
import time
import unicodedata
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from eodinga.common import FileRecord
from eodinga.observability import increment_counter, record_histogram
from eodinga.query.compiler import CompiledBranch, CompiledQuery
from eodinga.query.ranker import rank_results


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    file: FileRecord
    match_score: float
    snippet: str | None = None


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    hits: list[SearchHit]
    total_estimate: int
    elapsed_ms: float


class _ContentPresenceCache(NamedTuple):
    total_changes: int
    has_indexed_content: bool


_CONTENT_PRESENCE_BY_CONNECTION: dict[int, _ContentPresenceCache] = {}


@lru_cache(maxsize=256)
def _record_batch_sql(has_where: bool) -> str:
    sql = "SELECT files.* FROM files"
    if has_where:
        sql += " WHERE {where_sql}"
    sql += " ORDER BY files.name_lower ASC LIMIT ? OFFSET ?"
    return sql


@lru_cache(maxsize=256)
def _path_candidates_fts_sql(
    has_path_match_sql: bool,
    has_where_sql: bool,
    case_sensitive: bool,
) -> str:
    sql = """
        SELECT files.*
        FROM paths_fts
        JOIN files ON files.id = paths_fts.rowid
    """
    filters: list[str] = []
    if has_path_match_sql:
        filters.append("{path_match_sql}")
    if has_where_sql:
        filters.append("{where_sql}")
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if case_sensitive else "files.name_lower LIKE ?"
    sql += (
        f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END,"
        f" bm25(paths_fts, 8.0, 2.0, 1.0) ASC, {order_expr} ASC LIMIT ?"
    )
    return sql


@lru_cache(maxsize=256)
def _path_candidates_scan_sql(
    positive_term_count: int,
    has_where_sql: bool,
    case_sensitive: bool,
) -> str:
    sql = "SELECT files.* FROM files"
    filters: list[str] = []
    for _ in range(positive_term_count):
        if case_sensitive:
            filters.append("(instr(files.name, ?) > 0 OR instr(files.path, ?) > 0)")
        else:
            filters.append("(instr(lower(files.name), ?) > 0 OR instr(lower(files.path), ?) > 0)")
    if has_where_sql:
        filters.append("{where_sql}")
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if case_sensitive else "files.name_lower LIKE ?"
    sql += f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END, {order_expr} ASC LIMIT ?"
    return sql


@lru_cache(maxsize=256)
def _content_candidates_sql(has_where_sql: bool) -> str:
    sql = """
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
        WHERE {content_match_sql}
    """
    if has_where_sql:
        sql += " AND {where_sql}"
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC LIMIT ?"
    return sql


@lru_cache(maxsize=256)
def _auto_content_candidates_sql(has_where_sql: bool) -> str:
    sql = """
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
        WHERE content_fts MATCH ?
    """
    if has_where_sql:
        sql += " AND {where_sql}"
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC LIMIT ?"
    return sql


@lru_cache(maxsize=256)
def _content_backfill_sql(has_where_sql: bool) -> str:
    sql = """
        SELECT files.*
        FROM files
        JOIN content_map ON content_map.file_id = files.id
    """
    if has_where_sql:
        sql += " WHERE {where_sql}"
    sql += " ORDER BY files.name_lower ASC LIMIT ? OFFSET ?"
    return sql


def _row_to_record(row: Mapping[str, object]) -> FileRecord:
    payload = {key: row[key] for key in row.keys()}  # type: ignore[arg-type]
    payload["is_dir"] = bool(payload["is_dir"])
    payload["is_symlink"] = bool(payload["is_symlink"])
    return FileRecord.model_validate(payload)


def _make_flags(flag_text: str) -> int:
    flags = 0
    for flag in flag_text.lower():
        if flag == "i":
            flags |= re.IGNORECASE
        if flag == "m":
            flags |= re.MULTILINE
        if flag == "s":
            flags |= re.DOTALL
    return flags


def _text_matches(value: str, needle: str, case_sensitive: bool) -> bool:
    haystack = _normalize_search_text(value, case_sensitive=case_sensitive)
    normalized_needle = _normalize_search_text(needle, case_sensitive=case_sensitive)
    return normalized_needle in haystack


def _normalize_search_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def _fts_prefix_literal(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"*'


def _term_ok(text: str, term_value: str, case_sensitive: bool, negated: bool) -> bool:
    matched = _text_matches(text, term_value, case_sensitive)
    return not matched if negated else matched


def _regex_ok(
    text: str,
    pattern: str,
    flags: str,
    negated: bool,
    default_case_sensitive: bool,
) -> bool:
    compiled = re.compile(
        pattern,
        _make_flags(flags)
        | (0 if default_case_sensitive or "i" in flags.lower() else re.IGNORECASE),
    )
    matched = bool(compiled.search(text))
    return not matched if negated else matched


def _plain_term_matches_record(
    record: FileRecord,
    content_text: str,
    term_value: str,
    case_sensitive: bool,
) -> bool:
    target_text = f"{record.name} {record.parent_path} {record.path}"
    return _text_matches(target_text, term_value, case_sensitive) or (
        bool(content_text) and _text_matches(content_text, term_value, case_sensitive)
    )


def _filter_record(branch: CompiledBranch, record: FileRecord, content_text: str) -> bool:
    for term in branch.path_terms:
        matched = _plain_term_matches_record(
            record,
            content_text,
            term.value,
            branch.case_sensitive,
        )
        if term.negated and matched:
            return False
        if not term.negated and not matched:
            return False
    for term in branch.path_filters:
        if not _term_ok(str(record.path), term.value, branch.case_sensitive, term.negated):
            return False
    target_text = f"{record.name} {record.parent_path} {record.path}"
    for term in branch.content_terms:
        if not _term_ok(content_text, term.value, branch.case_sensitive, term.negated):
            return False
    for term in branch.path_regex_terms:
        if not _regex_ok(
            target_text,
            term.pattern,
            term.flags,
            term.negated,
            branch.case_sensitive,
        ):
            return False
    for term in branch.content_regex_terms:
        if not _regex_ok(
            content_text,
            term.pattern,
            term.flags,
            term.negated,
            branch.case_sensitive,
        ):
            return False
    return True


def _fetch_records(
    conn: sqlite3.Connection, where_sql: str, where_params: tuple[object, ...], limit: int
) -> dict[int, FileRecord]:
    return _fetch_record_batch(conn, where_sql, where_params, limit=limit, offset=0)


def _fetch_record_batch(
    conn: sqlite3.Connection,
    where_sql: str,
    where_params: tuple[object, ...],
    limit: int,
    offset: int,
) -> dict[int, FileRecord]:
    sql = _record_batch_sql(bool(where_sql)).format(where_sql=where_sql)
    rows = conn.execute(sql, (*where_params, limit, offset)).fetchall()
    return {row["id"]: _row_to_record(row) for row in rows}


def _windows_scope_variants(root_text: str) -> tuple[str, ...]:
    normalized = root_text.rstrip("/\\") or root_text
    variants: list[str] = []

    def add_variant(value: str) -> None:
        candidate = value.rstrip("/\\") or value
        if candidate and candidate not in variants:
            variants.append(candidate)

    def add_slash_forms(value: str) -> None:
        add_variant(value)
        add_variant(value.replace("\\", "/"))
        add_variant(value.replace("/", "\\"))

    def add_drive_letter_forms(value: str) -> None:
        add_slash_forms(value)
        if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
            add_slash_forms(value[0].upper() + value[1:])
            add_slash_forms(value[0].lower() + value[1:])

    raw = normalized
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    elif raw.startswith("//?/"):
        raw = raw[4:]

    add_drive_letter_forms(raw)
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        raw_backslashes = raw.replace("/", "\\")
        raw_forward = raw.replace("\\", "/")
        upper_drive = raw[0].upper() + raw[1:]
        lower_drive = raw[0].lower() + raw[1:]
        add_variant("\\\\?\\" + raw_backslashes)
        add_variant("//?/" + raw_forward)
        add_variant("\\\\?\\" + upper_drive.replace("/", "\\"))
        add_variant("\\\\?\\" + lower_drive.replace("/", "\\"))
        add_variant("//?/" + upper_drive.replace("\\", "/"))
        add_variant("//?/" + lower_drive.replace("\\", "/"))

    return tuple(variants)


def _root_scope_clause(root: Path | None) -> tuple[str, tuple[object, ...]]:
    if root is None:
        return "", ()
    variants = _windows_scope_variants(str(root))
    exact_params = variants
    like_params = tuple(f"{variant}/%" for variant in variants) + tuple(
        f"{variant}\\%" for variant in variants
    )
    exact_clause = " OR ".join("files.path = ?" for _ in exact_params)
    like_clause = " OR ".join("files.path LIKE ?" for _ in like_params)
    return f"({exact_clause} OR {like_clause})", (*exact_params, *like_params)


def _scoped_branch(branch: CompiledBranch, root: Path | None) -> CompiledBranch:
    scope_sql, scope_params = _root_scope_clause(root)
    if not scope_sql:
        return branch
    if branch.where_sql:
        where_sql = f"{branch.where_sql} AND {scope_sql}"
        where_params = (*branch.where_params, *scope_params)
    else:
        where_sql = scope_sql
        where_params = scope_params
    return branch.model_copy(update={"where_sql": where_sql, "where_params": where_params})


def _fetch_path_candidates(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord]]:
    ids, records = _fetch_path_candidates_fts(conn, branch, limit)
    if len(ids) >= limit or not _should_scan_path_candidates(branch, ids):
        return ids, records
    scan_ids, scan_records = _fetch_path_candidates_scan(conn, branch, limit)
    for file_id in scan_ids:
        if file_id in records:
            continue
        record = scan_records[file_id]
        records[file_id] = record
        ids.append(file_id)
        if len(ids) >= limit:
            break
    return ids, records


def _should_scan_path_candidates(branch: CompiledBranch, fts_ids: list[int]) -> bool:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return False
    if not fts_ids:
        return True
    # Keep the scan supplement for scripts where unicode token boundaries are less predictable.
    return any(any(ord(char) > 127 for char in term.value) for term in positive_terms)


def _fetch_path_candidates_fts(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return [], {}
    path_query = " ".join(_fts_prefix_literal(term.value) for term in positive_terms)
    params: list[object] = [path_query]
    prefix_term = positive_terms[0].value if positive_terms else ""
    if branch.where_sql:
        params.extend(branch.where_params)
    sql = _path_candidates_fts_sql(
        bool(branch.path_match_sql),
        bool(branch.where_sql),
        branch.case_sensitive,
    ).format(
        path_match_sql=branch.path_match_sql or "",
        where_sql=branch.where_sql,
    )
    params.append(f"{prefix_term}%")
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    return [row["id"] for row in rows], records


def _fetch_path_candidates_scan(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return [], {}
    if any(any(ord(char) > 127 for char in term.value) for term in positive_terms):
        return _fetch_path_candidates_python_scan(conn, branch, limit)
    params: list[object] = []
    prefix_term = positive_terms[0].value if positive_terms else ""
    for term in positive_terms:
        value = term.value if branch.case_sensitive else term.value.lower()
        params.extend([value, value])
    if branch.where_sql:
        params.extend(branch.where_params)
    sql = _path_candidates_scan_sql(
        len(positive_terms),
        bool(branch.where_sql),
        branch.case_sensitive,
    ).format(where_sql=branch.where_sql)
    params.append(f"{prefix_term}%")
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    return [row["id"] for row in rows], records


def _fetch_path_candidates_python_scan(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return [], {}
    records = _fetch_records(conn, branch.where_sql, branch.where_params, limit=100_000)
    matched = {
        file_id: record
        for file_id, record in records.items()
        if all(
            _text_matches(record.name, term.value, branch.case_sensitive)
            or _text_matches(str(record.path), term.value, branch.case_sensitive)
            for term in positive_terms
        )
    }
    ordered = sorted(
        matched.values(),
        key=lambda record: (
            0
            if any(
                _normalize_search_text(record.name, case_sensitive=branch.case_sensitive).startswith(
                    _normalize_search_text(term.value, case_sensitive=branch.case_sensitive)
                )
                for term in positive_terms
            )
            else 1,
            record.name if branch.case_sensitive else record.name_lower,
        ),
    )[:limit]
    ids = [record.id for record in ordered if record.id is not None]
    return ids, {record.id: record for record in ordered if record.id is not None}


def _fetch_content_candidates(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord], dict[int, str]]:
    if not branch.content_match_sql:
        return [], {}, {}
    params: list[object] = list(branch.content_match_params)
    if branch.where_sql:
        params.extend(branch.where_params)
    sql = _content_candidates_sql(bool(branch.where_sql)).format(
        content_match_sql=branch.content_match_sql,
        where_sql=branch.where_sql,
    )
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    snippets = {row["id"]: row["snippet"] for row in rows}
    ids = [row["id"] for row in rows]
    if len(ids) >= limit or not _should_scan_content_candidates(branch, ids):
        return ids, records, snippets
    scan_records = _scan_filtered_content_records(conn, branch, limit)
    for file_id, record in scan_records.items():
        if file_id in records:
            continue
        records[file_id] = record
        snippets[file_id] = None
        ids.append(file_id)
        if len(ids) >= limit:
            break
    return ids, records, snippets


def _fetch_auto_content_candidates(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord], dict[int, str]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if branch.content_required or not positive_terms:
        return [], {}, {}
    query = " ".join(f'"{term.value.replace(chr(34), chr(34) * 2)}"' for term in positive_terms)
    params: list[object] = [query]
    if branch.where_sql:
        params.extend(branch.where_params)
    sql = _auto_content_candidates_sql(bool(branch.where_sql)).format(where_sql=branch.where_sql)
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    snippets = {row["id"]: row["snippet"] for row in rows}
    ids = [row["id"] for row in rows]
    if len(ids) >= limit or not _should_scan_auto_content_candidates(branch, ids):
        return ids, records, snippets
    scan_records = _scan_auto_content_candidates(conn, branch, limit)
    for file_id, record in scan_records.items():
        if file_id in records:
            continue
        records[file_id] = record
        snippets[file_id] = None
        ids.append(file_id)
        if len(ids) >= limit:
            break
    return ids, records, snippets


def _should_scan_content_candidates(branch: CompiledBranch, fts_ids: list[int]) -> bool:
    positive_terms = [term for term in branch.content_terms if not term.negated]
    if not positive_terms:
        return False
    if not fts_ids:
        return True
    return any(any(ord(char) > 127 for char in term.value) for term in positive_terms)


def _should_scan_auto_content_candidates(branch: CompiledBranch, fts_ids: list[int]) -> bool:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return False
    if not fts_ids:
        return True
    return any(any(ord(char) > 127 for char in term.value) for term in positive_terms)


def _has_indexed_content(conn: sqlite3.Connection) -> bool:
    cached = _CONTENT_PRESENCE_BY_CONNECTION.get(id(conn))
    if cached is not None and cached.total_changes == conn.total_changes:
        return cached.has_indexed_content
    has_indexed_content = conn.execute("SELECT 1 FROM content_map LIMIT 1").fetchone() is not None
    _CONTENT_PRESENCE_BY_CONNECTION[id(conn)] = _ContentPresenceCache(
        total_changes=conn.total_changes,
        has_indexed_content=has_indexed_content,
    )
    return has_indexed_content


def _fetch_content_texts(conn: sqlite3.Connection, ids: Iterable[int]) -> dict[int, str]:
    id_list = tuple(dict.fromkeys(ids))
    if not id_list:
        return {}
    placeholders = ", ".join("?" for _ in id_list)
    sql = f"""
        SELECT content_map.file_id, content_fts.title, content_fts.head_text, content_fts.body_text
        FROM content_map
        JOIN content_fts ON content_fts.rowid = content_map.fts_rowid
        WHERE content_map.file_id IN ({placeholders})
    """
    rows = conn.execute(sql, id_list).fetchall()
    return {
        row["file_id"]: " ".join(
            part for part in (row["title"], row["head_text"], row["body_text"]) if part
        )
        for row in rows
    }


def _fetch_content_backfill(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> dict[int, FileRecord]:
    return _fetch_content_backfill_batch(conn, branch, limit=limit, offset=0)


def _fetch_content_backfill_batch(
    conn: sqlite3.Connection,
    branch: CompiledBranch,
    limit: int,
    offset: int,
) -> dict[int, FileRecord]:
    params: list[object] = []
    if branch.where_sql:
        params.extend(branch.where_params)
    sql = _content_backfill_sql(bool(branch.where_sql)).format(where_sql=branch.where_sql)
    rows = conn.execute(sql, (*params, limit, offset)).fetchall()
    return {row["id"]: _row_to_record(row) for row in rows}


def _scan_filtered_records(
    conn: sqlite3.Connection,
    branch: CompiledBranch,
    limit: int,
) -> dict[int, FileRecord]:
    target = max(limit, 1)
    batch_size = max(min(target * 2, 2000), 500)
    offset = 0
    matched: dict[int, FileRecord] = {}
    while len(matched) < target:
        batch = _fetch_record_batch(
            conn,
            branch.where_sql,
            branch.where_params,
            limit=batch_size,
            offset=offset,
        )
        if not batch:
            break
        content_texts = _fetch_content_texts(conn, batch) if _needs_record_filter(branch) else {}
        for file_id, record in batch.items():
            if _filter_record(branch, record, content_texts.get(file_id, "")):
                matched[file_id] = record
                if len(matched) >= target:
                    break
        offset += batch_size
    return matched


def _scan_filtered_content_records(
    conn: sqlite3.Connection,
    branch: CompiledBranch,
    limit: int,
) -> dict[int, FileRecord]:
    target = max(limit, 1)
    batch_size = max(min(target * 2, 2000), 500)
    offset = 0
    matched: dict[int, FileRecord] = {}
    while len(matched) < target:
        batch = _fetch_content_backfill_batch(conn, branch, limit=batch_size, offset=offset)
        if not batch:
            break
        content_texts = _fetch_content_texts(conn, batch)
        for file_id, record in batch.items():
            if _filter_record(branch, record, content_texts.get(file_id, "")):
                matched[file_id] = record
                if len(matched) >= target:
                    break
        offset += batch_size
    return matched


def _scan_auto_content_candidates(
    conn: sqlite3.Connection,
    branch: CompiledBranch,
    limit: int,
) -> dict[int, FileRecord]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if not positive_terms:
        return {}
    target = max(limit, 1)
    batch_size = max(min(target * 2, 2000), 500)
    offset = 0
    matched: dict[int, FileRecord] = {}
    while len(matched) < target:
        batch = _fetch_content_backfill_batch(conn, branch, limit=batch_size, offset=offset)
        if not batch:
            break
        content_texts = _fetch_content_texts(conn, batch)
        for file_id, record in batch.items():
            content_text = content_texts.get(file_id, "")
            if not all(
                _text_matches(content_text, term.value, branch.case_sensitive)
                for term in positive_terms
            ):
                continue
            matched[file_id] = record
            if len(matched) >= target:
                break
        offset += batch_size
    return matched


def _prefix_hits(records: Mapping[int, FileRecord], branch: CompiledBranch) -> list[int]:
    positives = [term.value for term in branch.path_terms if not term.negated]
    if not positives:
        return []
    hits: list[int] = []
    for file_id, record in records.items():
        check_name = _normalize_search_text(record.name, case_sensitive=branch.case_sensitive)
        for term in positives:
            needle = _normalize_search_text(term, case_sensitive=branch.case_sensitive)
            if check_name.startswith(needle):
                hits.append(file_id)
                break
    return hits


def _needs_record_filter(branch: CompiledBranch) -> bool:
    return bool(
        branch.path_filters
        or branch.path_regex_terms
        or branch.content_terms
        or branch.content_regex_terms
        or any(term.negated for term in branch.path_terms)
    )


def _is_metadata_only_branch(branch: CompiledBranch) -> bool:
    return not branch.path_match_sql and not branch.content_required and not _needs_record_filter(branch)


def _metadata_only_total_estimate(
    conn: sqlite3.Connection,
    branches: tuple[CompiledBranch, ...],
    *,
    cap: int = 10_000,
) -> int | None:
    if not branches or not all(_is_metadata_only_branch(branch) for branch in branches):
        return None
    selects: list[str] = []
    params: list[object] = []
    for branch in branches:
        select_sql = "SELECT files.id FROM files"
        if branch.where_sql:
            select_sql += f" WHERE {branch.where_sql}"
            params.extend(branch.where_params)
        selects.append(select_sql)
    union_sql = " UNION ".join(selects)
    row = conn.execute(
        f"SELECT COUNT(*) FROM ({union_sql} LIMIT {int(cap)}) AS metadata_matches",
        tuple(params),
    ).fetchone()
    return int(row[0]) if row is not None else 0


def _derive_name_path_hits(
    records: Mapping[int, FileRecord], branch: CompiledBranch
) -> tuple[list[int], list[int]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    name_hits: list[int] = []
    path_hits: list[int] = []
    if not positive_terms:
        ordered = sorted(records.values(), key=lambda item: item.name_lower)
        ids = [record.id for record in ordered if record.id is not None]
        return ids, ids
    for record in records.values():
        if record.id is None:
            continue
        target_name = record.name
        target_path = str(record.path)
        if any(
            _text_matches(target_name, term.value, branch.case_sensitive)
            for term in positive_terms
        ):
            name_hits.append(record.id)
        if any(
            _text_matches(target_path, term.value, branch.case_sensitive)
            for term in positive_terms
        ):
            path_hits.append(record.id)
    return name_hits, path_hits


def _execute_branch(
    conn: sqlite3.Connection,
    branch: CompiledBranch,
    limit: int,
    has_indexed_content: bool,
) -> tuple[dict[int, FileRecord], dict[int, float], dict[int, str | None]]:
    path_ids, path_records = _fetch_path_candidates(conn, branch, limit * 4)
    content_ids, content_records, snippets = _fetch_content_candidates(conn, branch, limit * 4)
    extra_records: dict[int, FileRecord] = {}
    if has_indexed_content:
        auto_content_ids, auto_content_records, auto_snippets = _fetch_auto_content_candidates(
            conn, branch, limit * 4
        )
    else:
        auto_content_ids, auto_content_records, auto_snippets = [], {}, {}
    if not content_ids:
        content_ids = auto_content_ids
        content_records = auto_content_records
        snippets = auto_snippets
    if branch.path_match_sql and branch.content_required:
        candidate_ids = set(path_ids) & set(content_ids or path_ids)
    elif branch.path_match_sql:
        candidate_ids = set(path_ids) | set(content_ids)
    elif branch.content_required:
        if content_ids:
            candidate_ids = set(content_ids)
        else:
            content_backfill = _scan_filtered_content_records(
                conn,
                branch,
                max(limit * 4, 1000),
            )
            extra_records = content_backfill
            candidate_ids = set(content_backfill)
    else:
        if _needs_record_filter(branch):
            scanned_records = _scan_filtered_records(conn, branch, max(limit * 4, 1000))
            extra_records = scanned_records
            candidate_ids = set(scanned_records)
        else:
            candidate_ids = set(
                _fetch_records(conn, branch.where_sql, branch.where_params, max(limit * 10, 1000))
            )
    records = {**path_records, **content_records, **extra_records}
    if not records and candidate_ids:
        records.update(
            _fetch_records(conn, branch.where_sql, branch.where_params, max(limit * 10, 1000))
        )
    if not candidate_ids and not branch.path_match_sql and not branch.content_required:
        candidate_ids = set(records)
    if _needs_record_filter(branch):
        content_texts = _fetch_content_texts(conn, candidate_ids)
        filtered_records = {
            file_id: records[file_id]
            for file_id in candidate_ids
            if file_id in records
            and _filter_record(branch, records[file_id], content_texts.get(file_id, ""))
        }
    else:
        filtered_records = {
            file_id: records[file_id] for file_id in candidate_ids if file_id in records
        }
    name_hits, path_hits = _derive_name_path_hits(filtered_records, branch)
    content_hits = [file_id for file_id in content_ids if file_id in filtered_records]
    prefix_hits = _prefix_hits(filtered_records, branch)
    scores = rank_results(
        name_hits=name_hits,
        path_hits=path_hits,
        content_hits=content_hits,
        prefix_hits=prefix_hits,
        paths={file_id: str(record.path) for file_id, record in filtered_records.items()},
    )
    branch_snippets = {file_id: snippets.get(file_id) for file_id in filtered_records}
    return filtered_records, scores, branch_snippets


def execute(
    conn: sqlite3.Connection,
    compiled: CompiledQuery,
    limit: int = 200,
    root: Path | None = None,
) -> QueryResult:
    started = time.perf_counter()
    merged_records: dict[int, FileRecord] = {}
    merged_scores: dict[int, float] = {}
    merged_snippets: dict[int, str | None] = {}
    has_indexed_content = _has_indexed_content(conn)
    scoped_branches = tuple(_scoped_branch(branch, root) for branch in compiled.branches)
    for scoped_branch in scoped_branches:
        branch_records, branch_scores, branch_snippets = _execute_branch(
            conn,
            scoped_branch,
            limit,
            has_indexed_content=has_indexed_content,
        )
        merged_records.update(branch_records)
        for file_id, score in branch_scores.items():
            merged_scores[file_id] = max(score, merged_scores.get(file_id, 0.0))
        for file_id, snippet in branch_snippets.items():
            if snippet and not merged_snippets.get(file_id):
                merged_snippets[file_id] = snippet
    ordered_ids = sorted(
        merged_scores,
        key=lambda file_id: (-merged_scores[file_id], merged_records[file_id].name_lower, file_id),
    )[:limit]
    hits = [
        SearchHit(
            file=merged_records[file_id],
            match_score=merged_scores[file_id],
            snippet=merged_snippets.get(file_id),
        )
        for file_id in ordered_ids
    ]
    elapsed_ms = (time.perf_counter() - started) * 1000
    total_estimate = _metadata_only_total_estimate(conn, scoped_branches)
    if total_estimate is None:
        total_estimate = len(merged_scores)
    increment_counter("queries_served")
    record_histogram("query_latency_ms", elapsed_ms)
    return QueryResult(hits=hits, total_estimate=total_estimate, elapsed_ms=elapsed_ms)


__all__ = ["QueryResult", "SearchHit", "execute"]
