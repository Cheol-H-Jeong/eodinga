from __future__ import annotations

import re
import sqlite3
import time
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from eodinga.common import FileRecord
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


def _filter_record(branch: CompiledBranch, record: FileRecord, content_text: str) -> bool:
    target_text = f"{record.name} {record.parent_path} {record.path}"
    for term in branch.path_terms:
        if term.negated:
            if not _term_ok(target_text, term.value, branch.case_sensitive, True):
                return False
            continue
        if _text_matches(target_text, term.value, branch.case_sensitive):
            continue
        if content_text and _text_matches(content_text, term.value, branch.case_sensitive):
            continue
        return False
    for term in branch.path_filters:
        if not _term_ok(str(record.path), term.value, branch.case_sensitive, term.negated):
            return False
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
    sql = "SELECT files.* FROM files"
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY files.name_lower ASC LIMIT ?"
    rows = conn.execute(sql, (*where_params, limit)).fetchall()
    return {row["id"]: _row_to_record(row) for row in rows}


def _root_scope_clause(root: Path | None) -> tuple[str, tuple[object, ...]]:
    if root is None:
        return "", ()
    root_text = str(root)
    normalized = root_text.rstrip("/\\") or root_text
    variants = tuple(
        dict.fromkeys(
            (
                normalized,
                normalized.replace("\\", "/"),
                normalized.replace("/", "\\"),
            )
        )
    )
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
    sql = """
        SELECT files.*
        FROM paths_fts
        JOIN files ON files.id = paths_fts.rowid
    """
    params: list[object] = [path_query]
    filters: list[str] = []
    if branch.path_match_sql:
        filters.append(branch.path_match_sql)
    prefix_term = positive_terms[0].value if positive_terms else ""
    if branch.where_sql:
        filters.append(branch.where_sql)
        params.extend(branch.where_params)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if branch.case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if branch.case_sensitive else "files.name_lower LIKE ?"
    sql += (
        f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END,"
        f" bm25(paths_fts, 8.0, 2.0, 1.0) ASC, {order_expr} ASC LIMIT ?"
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
    sql = "SELECT files.* FROM files"
    params: list[object] = []
    filters: list[str] = []
    prefix_term = positive_terms[0].value if positive_terms else ""
    for term in positive_terms:
        if branch.case_sensitive:
            filters.append("(instr(files.name, ?) > 0 OR instr(files.path, ?) > 0)")
            params.extend([term.value, term.value])
        else:
            filters.append("(instr(lower(files.name), ?) > 0 OR instr(lower(files.path), ?) > 0)")
            lowered = term.value.lower()
            params.extend([lowered, lowered])
    if branch.where_sql:
        filters.append(branch.where_sql)
        params.extend(branch.where_params)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    order_expr = "files.name" if branch.case_sensitive else "files.name_lower"
    prefix_expr = "files.name LIKE ?" if branch.case_sensitive else "files.name_lower LIKE ?"
    sql += f" ORDER BY CASE WHEN {prefix_expr} THEN 0 ELSE 1 END, {order_expr} ASC LIMIT ?"
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
    sql = """
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
    """
    params: list[object] = list(branch.content_match_params)
    filters: list[str] = [branch.content_match_sql]
    if branch.where_sql:
        filters.append(branch.where_sql)
        params.extend(branch.where_params)
    sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC LIMIT ?"
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    snippets = {row["id"]: row["snippet"] for row in rows}
    return [row["id"] for row in rows], records, snippets


def _fetch_auto_content_candidates(
    conn: sqlite3.Connection, branch: CompiledBranch, limit: int
) -> tuple[list[int], dict[int, FileRecord], dict[int, str]]:
    positive_terms = [term for term in branch.path_terms if not term.negated]
    if branch.content_required or not positive_terms:
        return [], {}, {}
    query = " ".join(f'"{term.value.replace(chr(34), chr(34) * 2)}"' for term in positive_terms)
    sql = """
        SELECT files.*, snippet(content_fts, 2, '[', ']', '...', 12) AS snippet
        FROM content_fts
        JOIN content_map ON content_map.fts_rowid = content_fts.rowid
        JOIN files ON files.id = content_map.file_id
    """
    params: list[object] = [query]
    filters = ["content_fts MATCH ?"]
    if branch.where_sql:
        filters.append(branch.where_sql)
        params.extend(branch.where_params)
    sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY bm25(content_fts, 3.0, 1.5, 1.0) ASC LIMIT ?"
    rows = conn.execute(sql, (*params, limit)).fetchall()
    records = {row["id"]: _row_to_record(row) for row in rows}
    snippets = {row["id"]: row["snippet"] for row in rows}
    return [row["id"] for row in rows], records, snippets


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
    sql = """
        SELECT files.*
        FROM files
        JOIN content_map ON content_map.file_id = files.id
    """
    params: list[object] = []
    if branch.where_sql:
        sql += " WHERE " + branch.where_sql
        params.extend(branch.where_params)
    sql += " ORDER BY files.name_lower ASC LIMIT ?"
    rows = conn.execute(sql, (*params, limit)).fetchall()
    return {row["id"]: _row_to_record(row) for row in rows}


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
            content_backfill = _fetch_content_backfill(conn, branch, max(limit * 10, 1000))
            extra_records = content_backfill
            candidate_ids = set(content_backfill)
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
    for branch in compiled.branches:
        scoped_branch = _scoped_branch(branch, root)
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
    return QueryResult(hits=hits, total_estimate=len(merged_scores), elapsed_ms=elapsed_ms)


__all__ = ["QueryResult", "SearchHit", "execute"]
