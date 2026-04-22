from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from time import time

from eodinga.common import FileRecord, ParsedContent, WatchEvent
from eodinga.index.schema import apply_schema, current_schema_version

ParserCallback = Callable[[Path], ParsedContent | None]
RecordLoader = Callable[[Path], FileRecord | None]


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


class IndexWriter:
    def __init__(
        self, conn: sqlite3.Connection, parser_callback: ParserCallback | None = None
    ) -> None:
        self._conn = conn
        self._parser_callback = parser_callback or (lambda _path: None)
        if current_schema_version(self._conn) == 0:
            apply_schema(self._conn)

    def bulk_upsert(self, records: Iterable[FileRecord]) -> int:
        buffered = list(records)
        if not buffered:
            return 0
        with self._conn:
            self._upsert_records(buffered)
            self._upsert_content(buffered)
        return len(buffered)

    def apply_events(self, events: Sequence[WatchEvent], record_loader: RecordLoader) -> int:
        processed = 0
        content_deletes: list[int] = []
        with self._conn:
            for event in events:
                if event.event_type == "deleted":
                    processed += self._delete_path(event.path, content_deletes)
                    continue
                if event.event_type == "moved" and event.src_path is not None:
                    self._delete_path(event.src_path, content_deletes)
                record = record_loader(event.path)
                if record is None:
                    continue
                self._upsert_records([record])
                self._upsert_content([record])
                processed += 1
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
              content_hash=excluded.content_hash,
              indexed_at=excluded.indexed_at
            """,
            [_record_tuple(record) for record in records],
        )

    def _delete_path(self, path: Path, content_deletes: list[int]) -> int:
        row = self._conn.execute(
            "SELECT fts_rowid FROM content_map "
            "JOIN files ON files.id = content_map.file_id "
            "WHERE files.path = ?",
            (str(path),),
        ).fetchone()
        if row is not None:
            content_deletes.append(int(row[0]))
        cursor = self._conn.execute("DELETE FROM files WHERE path = ?", (str(path),))
        return cursor.rowcount

    def _upsert_content(self, records: Sequence[FileRecord]) -> None:
        for record in records:
            if record.is_dir:
                continue
            parsed = self._parser_callback(record.path)
            if parsed is None:
                continue
            existing = self._conn.execute(
                "SELECT id FROM files WHERE path = ?",
                (str(record.path),),
            ).fetchone()
            if existing is None:
                continue
            file_id = int(existing[0])
            current = self._conn.execute(
                "SELECT fts_rowid FROM content_map WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if current is not None:
                self._conn.execute("DELETE FROM content_fts WHERE rowid = ?", (int(current[0]),))
                rowid = int(current[0])
            else:
                rowid_query = "SELECT COALESCE(MAX(rowid), 0) + 1 FROM content_fts"
                rowid = int(self._conn.execute(rowid_query).fetchone()[0])
            self._conn.execute(
                "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
                (rowid, parsed.title, parsed.head_text, parsed.body_text),
            )
            self._conn.execute(
                """
                INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                  fts_rowid=excluded.fts_rowid,
                  parser=excluded.parser,
                  parsed_at=excluded.parsed_at,
                  content_sha=excluded.content_sha
                """,
                (file_id, rowid, "injected", int(time()), parsed.content_sha),
            )

    def _delete_content_rows(self, rowids: Sequence[int]) -> None:
        self._conn.executemany(
            "DELETE FROM content_fts WHERE rowid = ?",
            [(rowid,) for rowid in rowids],
        )
