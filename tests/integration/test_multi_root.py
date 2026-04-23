from __future__ import annotations

from pathlib import Path

from eodinga.config import RootConfig
from eodinga.index import open_index
from eodinga.index.build import rebuild_index
from eodinga.query import search


def test_multi_root_rebuild_indexes_all_roots_and_respects_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-shared.txt").write_text("shared launch note\n", encoding="utf-8")
    (root_b / "beta-shared.txt").write_text("shared launch note\n", encoding="utf-8")
    (root_b / "beta-only.txt").write_text("beta only content\n", encoding="utf-8")

    result = rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    assert result.roots_indexed == 2

    conn = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(conn, "shared launch", limit=10).hits}
        alpha_hits = {hit.file.path for hit in search(conn, "shared launch", limit=10, root=root_a).hits}
        beta_hits = {hit.file.path for hit in search(conn, "shared launch", limit=10, root=root_b).hits}
        stored_roots = {
            Path(row[0]) for row in conn.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
        indexed_files = conn.execute("SELECT COUNT(*) FROM files WHERE is_dir = 0").fetchone()
    finally:
        conn.close()

    assert hits == {root_a / "alpha-shared.txt", root_b / "beta-shared.txt"}
    assert alpha_hits == {root_a / "alpha-shared.txt"}
    assert beta_hits == {root_b / "beta-shared.txt"}
    assert stored_roots == {root_a, root_b}
    assert indexed_files is not None and int(indexed_files[0]) == 3


def test_multi_root_rebuild_replaces_removed_root_content_and_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-keep.txt"
    beta = root_b / "beta-drop.txt"
    alpha.write_text("shared rebuild survivor\n", encoding="utf-8")
    beta.write_text("shared rebuild survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    conn = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10).hits}
        alpha_hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10, root=root_a).hits}
        beta_hits = {hit.file.path for hit in search(conn, "shared rebuild survivor", limit=10, root=root_b).hits}
        stored_roots = {
            Path(row[0]) for row in conn.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        conn.close()

    assert hits == {alpha}
    assert alpha_hits == {alpha}
    assert beta_hits == set()
    assert stored_roots == {root_a}


def test_multi_root_rebuild_indexes_nested_files_across_roots_and_scopes(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    alpha_nested = root_a / "incoming" / "batch"
    beta_nested = root_b / "archive" / "batch"
    alpha_nested.mkdir(parents=True)
    beta_nested.mkdir(parents=True)
    alpha = alpha_nested / "alpha-nested.txt"
    beta = beta_nested / "beta-nested.txt"
    alpha.write_text("nested multi root alpha coverage\n", encoding="utf-8")
    beta.write_text("nested multi root beta coverage\n", encoding="utf-8")

    result = rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )

    assert result.roots_indexed == 2

    conn = open_index(db_path)
    try:
        all_hits = {hit.file.path for hit in search(conn, "nested multi root", limit=10).hits}
        alpha_hits = {hit.file.path for hit in search(conn, "nested multi root", limit=10, root=root_a).hits}
        beta_hits = {hit.file.path for hit in search(conn, "nested multi root", limit=10, root=root_b).hits}
        alpha_path_hits = {hit.file.path for hit in search(conn, "path:alpha-nested", limit=10).hits}
        beta_path_hits = {hit.file.path for hit in search(conn, "path:beta-nested", limit=10).hits}
    finally:
        conn.close()

    assert all_hits == {alpha, beta}
    assert alpha_hits == {alpha}
    assert beta_hits == {beta}
    assert alpha_path_hits == {alpha}
    assert beta_path_hits == {beta}


def test_multi_root_reopen_after_removed_root_rebuild_keeps_trimmed_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-survivor.txt"
    beta = root_b / "beta-pruned.txt"
    alpha.write_text("reopen trimmed root survivor\n", encoding="utf-8")
    beta.write_text("reopen trimmed root survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    try:
        hits = {hit.file.path for hit in search(reopened, "reopen trimmed root survivor", limit=10).hits}
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "reopen trimmed root survivor", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "reopen trimmed root survivor", limit=10, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        reopened.close()

    assert hits == {alpha}
    assert alpha_hits == {alpha}
    assert beta_hits == set()
    assert stored_roots == {root_a}


def test_multi_root_reopen_preserves_nested_scope_after_trimmed_rebuild(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"

    alpha_nested = root_a / "incoming" / "batch"
    beta_nested = root_b / "incoming" / "batch"
    alpha_nested.mkdir(parents=True)
    beta_nested.mkdir(parents=True)
    alpha = alpha_nested / "alpha-survivor.txt"
    beta = beta_nested / "beta-pruned.txt"
    alpha.write_text("nested reopen trimmed root survivor\n", encoding="utf-8")
    beta.write_text("nested reopen trimmed root survivor\n", encoding="utf-8")

    rebuild_index(
        db_path,
        [RootConfig(path=root_a), RootConfig(path=root_b)],
        content_enabled=True,
    )
    rebuild_index(db_path, [RootConfig(path=root_a)], content_enabled=True)

    reopened = open_index(db_path)
    try:
        all_hits = {hit.file.path for hit in search(reopened, "nested reopen trimmed root survivor", limit=10).hits}
        alpha_hits = {
            hit.file.path
            for hit in search(reopened, "nested reopen trimmed root survivor", limit=10, root=root_a).hits
        }
        beta_hits = {
            hit.file.path
            for hit in search(reopened, "nested reopen trimmed root survivor", limit=10, root=root_b).hits
        }
        stored_roots = {
            Path(row[0]) for row in reopened.execute("SELECT path FROM roots ORDER BY id").fetchall()
        }
    finally:
        reopened.close()

    assert all_hits == {alpha}
    assert alpha_hits == {alpha}
    assert beta_hits == set()
    assert stored_roots == {root_a}
