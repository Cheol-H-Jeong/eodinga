from __future__ import annotations

from pathlib import Path
from queue import Empty

import pytest

from eodinga.common import PathRules, WatchEvent
from eodinga.content.registry import parse
from eodinga.core.walker import walk_batched
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from eodinga.query import search
from tests.conftest import make_record


def _is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in ("w", "a", "+", "x"))


def test_runtime_never_writes_user_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_root = tmp_path / "user-root"
    docs = user_root / "docs"
    docs.mkdir(parents=True)
    target = docs / "guide.txt"
    target.write_text("guide body\nlauncher query\n", encoding="utf-8")

    db_path = tmp_path / "database" / "index.db"
    conn = open_index(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(user_root), "[]", "[]", 1),
        )
        conn.commit()

        original_open = Path.open
        attempted_writes: list[tuple[Path, str]] = []

        def guarded_open(
            self: Path,
            mode: str = "r",
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ):
            if self.is_relative_to(user_root) and _is_write_mode(mode):
                attempted_writes.append((self, mode))
                raise AssertionError(f"unexpected write under user root: {self} [{mode}]")
            return original_open(
                self,
                mode=mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        monkeypatch.setattr(Path, "open", guarded_open)

        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        records = [
            record
            for batch in walk_batched(user_root, PathRules(root=user_root), root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)

        service = WatchService()
        service.record(WatchEvent(event_type="modified", path=target, root_path=user_root))
        service._flush_ready(force=True)
        event = service.queue.get_nowait()
        assert writer.apply_events([event], record_loader=make_record) == 1

        result = search(conn, "launcher", limit=5)
        names = [hit.file.name for hit in result.hits]
        assert "guide.txt" in names
        assert attempted_writes == []

        with pytest.raises(Empty):
            service.queue.get_nowait()
    finally:
        conn.close()
