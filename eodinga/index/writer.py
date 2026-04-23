from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from time import time
from typing import NamedTuple, TypeVar

from eodinga.common import FileRecord, ParsedContent, WatchEvent
from eodinga.index.schema import apply_schema, current_schema_version

ParserCallback = Callable[[Path], ParsedContent | None]
RecordLoader = Callable[[Path], FileRecord | None]
T = TypeVar("T")


class ExistingContentRow(NamedTuple):
    file_id: int
    rowid: int | None
    content_sha: bytes | None


def _record_tuple(record: FileRecord) -> tuple[object, ...]:
    return (
        record.root_id,
        str(record.path),
        str(record.parent_path),
        record.name,
        record.name_lower,
        record.ext,
        record.size,
        record.mtime,
        record.ctime,
        int(record.is_dir),
        int(record.is_symlink),
        record.content_hash,
        record.indexed_at,
    )


def _chunked(values: Sequence[T], size: int = 500) -> Iterable[Sequence[T]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _materialize_records(records: Iterable[FileRecord]) -> Sequence[FileRecord]:
    if isinstance(records, (list, tuple)):
        return records
    return tuple(records)


class IndexWriter:
    def __init__(
        self, conn: sqlite3.Connection, parser_callback: ParserCallback | None = None
    ) -> None:
        self._conn = conn
        self._parser_callback = parser_callback
        if current_schema_version(self._conn) == 0:
            apply_schema(self._conn)

    def bulk_upsert(self, records: Iterable[FileRecord]) -> int:
        buffered = _materialize_records(records)
        if not buffered:
            return 0
        with self._conn:
            self._upsert_records(buffered)
            self._upsert_content(buffered)
        return len(buffered)

    def apply_events(self, events: Sequence[WatchEvent], record_loader: RecordLoader) -> int:
        processed = 0
        content_deletes: list[int] = []
        deleted_paths: list[Path] = []
        retired_paths: list[Path] = []
        pending_records: list[FileRecord] = []
        root_ids_by_path = self._root_ids_for_watch_paths(events)
        with self._conn:
            for event in events:
                if event.event_type == "deleted":
                    deleted_paths.append(event.path)
                    continue
                if event.event_type == "moved" and event.src_path is not None:
                    retired_paths.append(event.src_path)
                record = record_loader(event.path)
                if record is None:
                    continue
                root_id = (
                    root_ids_by_path.get(event.root_path)
                    if event.root_path is not None
                    else None
                )
                if root_id is not None and record.root_id != root_id:
                    record = record.model_copy(update={"root_id": root_id})
                pending_records.append(record)
                processed += 1
            if deleted_paths:
                processed += self._delete_paths(deleted_paths, content_deletes)
            if retired_paths:
                self._delete_paths(retired_paths, content_deletes)
            if pending_records:
                self._upsert_records(pending_records)
                self._upsert_content(pending_records)
            if content_deletes:
                self._delete_content_rows(content_deletes)
        return processed

    def _upsert_records(self, records: Sequence[FileRecord]) -> None:
        self._conn.executemany(
            """
            INSERT INTO files(
              root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
              is_dir, is_symlink, content_hash, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              root_id=excluded.root_id,
              parent_path=excluded.parent_path,
              name=excluded.name,
              name_lower=excluded.name_lower,
              ext=excluded.ext,
              size=excluded.size,
              mtime=excluded.mtime,
              ctime=excluded.ctime,
              is_dir=excluded.is_dir,
              is_symlink=excluded.is_symlink,
              content_hash=COALESCE(excluded.content_hash, files.content_hash),
              indexed_at=excluded.indexed_at
            """,
            (_record_tuple(record) for record in records),
        )

    def _delete_path(self, path: Path, content_deletes: list[int]) -> int:
        return self._delete_paths((path,), content_deletes)

    def _delete_paths(self, paths: Sequence[Path], content_deletes: list[int]) -> int:
        unique_paths = tuple(dict.fromkeys(str(path) for path in paths))
        if not unique_paths:
            return 0
        deleted = 0
        for chunk in _chunked(unique_paths):
            placeholders = ", ".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"""
                SELECT content_map.fts_rowid
                FROM files
                JOIN content_map ON content_map.file_id = files.id
                WHERE files.path IN ({placeholders})
                """,
                tuple(chunk),
            ).fetchall()
            content_deletes.extend(int(row[0]) for row in rows)
            cursor = self._conn.execute(
                f"DELETE FROM files WHERE path IN ({placeholders})",
                tuple(chunk),
            )
            deleted += cursor.rowcount
        return deleted

    def _upsert_content(self, records: Sequence[FileRecord]) -> None:
        if self._parser_callback is None:
            return
        parsed_by_path: dict[str, ParsedContent] = {}
        path_order: list[str] = []
        for record in records:
            if record.is_dir:
                continue
            parsed = self._parser_callback(record.path)
            if parsed is None:
                continue
            path_text = str(record.path)
            parsed_by_path[path_text] = parsed
            path_order.append(path_text)
        if not parsed_by_path:
            return

        existing_rows = self._select_existing_content_rows(path_order)
        if not existing_rows:
            return
        changed_paths = [
            path_text
            for path_text in path_order
            if path_text in existing_rows
            and existing_rows[path_text].content_sha != (parsed_by_path[path_text].content_sha or None)
        ]
        reused_rowids = [
            row.rowid
            for path_text in changed_paths
            if (row := existing_rows[path_text]).rowid is not None
        ]
        if reused_rowids:
            self._delete_content_rows(reused_rowids)

        next_rowid: int | None = None
        content_rows: list[tuple[object, ...]] = []
        mapping_rows: list[tuple[object, ...]] = []
        hash_rows: list[tuple[object, ...]] = []
        now = int(time())
        for path_text in path_order:
            row = existing_rows.get(path_text)
            parsed = parsed_by_path[path_text]
            parsed_sha = parsed.content_sha or None
            if row is None:
                continue
            file_id = row.file_id
            rowid = row.rowid
            if row.content_sha == parsed_sha:
                continue
            if rowid is None:
                if next_rowid is None:
                    next_rowid = self._next_content_rowid()
                rowid = next_rowid
                assert rowid is not None
                next_rowid += 1
            content_rows.append((rowid, parsed.title, parsed.head_text, parsed.body_text))
            mapping_rows.append((file_id, rowid, "injected", now, parsed.content_sha))
            hash_rows.append((parsed_sha, file_id))

        if content_rows:
            self._conn.executemany(
                "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
                content_rows,
            )
            self._conn.executemany(
                """
                INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                  fts_rowid=excluded.fts_rowid,
                  parser=excluded.parser,
                  parsed_at=excluded.parsed_at,
                  content_sha=excluded.content_sha
                """,
                mapping_rows,
            )
            self._conn.executemany(
                "UPDATE files SET content_hash = ? WHERE id = ?",
                hash_rows,
            )

    def _select_existing_content_rows(self, paths: Sequence[str]) -> dict[str, ExistingContentRow]:
        results: dict[str, ExistingContentRow] = {}
        for chunk in _chunked(paths):
            placeholders = ", ".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"""
                SELECT files.path, files.id, content_map.fts_rowid, content_map.content_sha
                FROM files
                LEFT JOIN content_map ON content_map.file_id = files.id
                WHERE files.path IN ({placeholders})
                """,
                tuple(chunk),
            ).fetchall()
            for row in rows:
                rowid = row[2]
                results[str(row[0])] = ExistingContentRow(
                    file_id=int(row[1]),
                    rowid=int(rowid) if rowid is not None else None,
                    content_sha=bytes(row[3]) if row[3] is not None else None,
                )
        return results

    def _next_content_rowid(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(rowid), 0) + 1 FROM content_fts").fetchone()
        return int(row[0])

    def _delete_content_rows(self, rowids: Sequence[int]) -> None:
        for chunk in _chunked(tuple(dict.fromkeys(rowids))):
            placeholders = ", ".join("?" for _ in chunk)
            self._conn.execute(
                f"DELETE FROM content_fts WHERE rowid IN ({placeholders})",
                tuple(chunk),
            )

    def _root_ids_for_watch_paths(self, events: Sequence[WatchEvent]) -> dict[Path, int]:
        root_paths = tuple(
            dict.fromkeys(event.root_path for event in events if event.root_path is not None)
        )
        if not root_paths:
            return {}
        root_ids_by_text = self._root_ids_by_text(root_paths)
        return {root_path: root_ids_by_text[str(root_path)] for root_path in root_paths if str(root_path) in root_ids_by_text}

    def _root_ids_by_text(self, root_paths: Sequence[Path]) -> dict[str, int]:
        root_texts = tuple(dict.fromkeys(str(path) for path in root_paths))
        if not root_texts:
            return {}
        results: dict[str, int] = {}
        for chunk in _chunked(root_texts):
            placeholders = ", ".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT id, path FROM roots WHERE path IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
            for row in rows:
                results[str(row[1])] = int(row[0])
        return results
