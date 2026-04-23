from __future__ import annotations

from pathlib import Path

from eodinga.__main__ import _load_watch_roots, _resolve_watch_root_id, _watch_record_loader
from eodinga.index import open_index


def test_load_watch_roots_returns_enabled_rows_in_id_order(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    conn = open_index(db_path)
    try:
        conn.executemany(
            """
            INSERT INTO roots(id, path, include, exclude, enabled, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (2, str(tmp_path / "beta"), "[]", "[]", 1, 2),
                (1, str(tmp_path / "alpha"), "[]", "[]", 1, 1),
                (3, str(tmp_path / "disabled"), "[]", "[]", 0, 3),
            ),
        )
        conn.commit()

        roots = _load_watch_roots(conn)
    finally:
        conn.close()

    assert roots == [
        (1, tmp_path / "alpha"),
        (2, tmp_path / "beta"),
    ]


def test_resolve_watch_root_id_prefers_event_root_then_longest_prefix(tmp_path: Path) -> None:
    alpha = tmp_path / "alpha"
    nested = alpha / "nested"
    beta = tmp_path / "beta"
    root_ids = {
        alpha: 1,
        nested: 2,
        beta: 3,
    }

    assert _resolve_watch_root_id(
        nested / "doc.txt",
        root_ids,
        event_root=alpha,
    ) == 1
    assert _resolve_watch_root_id(nested / "doc.txt", root_ids) == 2
    assert _resolve_watch_root_id(tmp_path / "missing" / "doc.txt", root_ids) is None


def test_watch_record_loader_materializes_file_metadata_for_matching_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "note.txt"
    target.write_text("watch me\n", encoding="utf-8")

    record = _watch_record_loader(
        target,
        root_ids={root: 7},
        event_root=root,
    )

    assert record is not None
    assert record.root_id == 7
    assert record.path == target
    assert record.parent_path == root
    assert record.name == "note.txt"
    assert record.name_lower == "note.txt"
    assert record.ext == "txt"
    assert record.is_dir is False
    assert record.is_symlink is False


def test_watch_record_loader_ignores_missing_paths_and_untracked_roots(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    missing = root / "missing.txt"

    assert _watch_record_loader(missing, root_ids={root: 1}, event_root=root) is None
    assert _watch_record_loader(missing, root_ids={tmp_path / "other": 2}, event_root=None) is None
