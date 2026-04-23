from __future__ import annotations

import json
from pathlib import Path
from queue import Empty
from time import monotonic

from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from tests.conftest import make_record


def _json_payload(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


def _search_paths(cli_runner, db_path: Path, query: str, *, root: Path | None = None) -> list[Path]:
    args = ["--db", str(db_path), "search", query, "--json"]
    if root is not None:
        args.extend(["--root", str(root)])
    result = cli_runner(*args)
    assert result.returncode == 0
    return [Path(item["path"]) for item in _json_payload(result.stdout)["results"]]


def _wait_for_cli_hit(
    cli_runner,
    db_path: Path,
    service: WatchService,
    writer: IndexWriter,
    query: str,
    expected_path: Path,
    *,
    root: Path | None = None,
    deadline_seconds: float = 0.5,
) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        try:
            event = service.queue.get(timeout=0.05)
        except Empty:
            continue
        writer.apply_events([event], record_loader=make_record)
        if expected_path in _search_paths(cli_runner, db_path, query, root=root):
            return min(monotonic() - started, deadline_seconds)
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def test_cli_multi_root_index_and_root_scoped_search(cli_runner, tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-shared.txt"
    beta = root_b / "beta-shared.txt"
    alpha.write_text("shared cli integration marker\n", encoding="utf-8")
    beta.write_text("shared cli integration marker\n", encoding="utf-8")
    (root_b / "beta-only.txt").write_text("beta only integration marker\n", encoding="utf-8")

    index_result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
        "--rebuild",
    )

    assert index_result.returncode == 0
    index_payload = _json_payload(index_result.stdout)
    assert index_payload["command"] == "index"
    assert index_payload["db"] == str(db_path)
    assert index_payload["roots"] == [str(root_a), str(root_b)]
    assert int(index_payload["files_indexed"]) >= 3

    global_search = cli_runner(
        "--db",
        str(db_path),
        "search",
        "shared cli integration marker",
        "--json",
    )
    beta_search = cli_runner(
        "--db",
        str(db_path),
        "search",
        "shared cli integration marker",
        "--json",
        "--root",
        str(root_b),
    )

    assert global_search.returncode == 0
    assert beta_search.returncode == 0
    global_paths = {Path(item["path"]) for item in _json_payload(global_search.stdout)["results"]}
    beta_paths = {Path(item["path"]) for item in _json_payload(beta_search.stdout)["results"]}
    assert global_paths == {alpha, beta}
    assert beta_paths == {beta}


def test_cli_rebuild_drops_removed_root_content_from_followup_search(
    cli_runner,
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"

    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-keep.txt"
    beta = root_b / "beta-drop.txt"
    alpha.write_text("shared rebuild cli marker\n", encoding="utf-8")
    beta.write_text("shared rebuild cli marker\n", encoding="utf-8")

    first_index = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
        "--rebuild",
    )
    rebuild = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--rebuild",
    )
    global_search = cli_runner(
        "--db",
        str(db_path),
        "search",
        "shared rebuild cli marker",
        "--json",
    )
    beta_search = cli_runner(
        "--db",
        str(db_path),
        "search",
        "shared rebuild cli marker",
        "--json",
        "--root",
        str(root_b),
    )

    assert first_index.returncode == 0
    assert rebuild.returncode == 0
    assert global_search.returncode == 0
    assert beta_search.returncode == 0
    global_paths = {Path(item["path"]) for item in _json_payload(global_search.stdout)["results"]}
    beta_paths = {Path(item["path"]) for item in _json_payload(beta_search.stdout)["results"]}
    assert global_paths == {alpha}
    assert beta_paths == set()


def test_cli_live_update_visible_within_500ms_after_cli_index(cli_runner, tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "index.db"
    root.mkdir()
    (root / "seed.txt").write_text("cli indexed seed\n", encoding="utf-8")

    index_result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    assert index_result.returncode == 0

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "live-update.txt"
        created.write_text("cli watcher integration update\n", encoding="utf-8")
        elapsed = _wait_for_cli_hit(
            cli_runner,
            db_path,
            service,
            writer,
            "cli watcher integration update",
            created,
        )
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5


def test_cli_hot_restart_reopen_keeps_searchable_content_and_accepts_live_updates(
    cli_runner,
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "index.db"
    root.mkdir()
    existing = root / "persisted.txt"
    existing.write_text("cli persisted restart marker\n", encoding="utf-8")

    index_result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    assert index_result.returncode == 0
    assert _search_paths(cli_runner, db_path, "cli persisted restart marker") == [existing]

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-reopen.txt"
        created.write_text("cli restart live update\n", encoding="utf-8")
        elapsed = _wait_for_cli_hit(
            cli_runner,
            db_path,
            service,
            writer,
            "cli restart live update",
            created,
        )
        persisted_paths = _search_paths(cli_runner, db_path, "cli persisted restart marker")
    finally:
        service.stop()
        reopened.close()

    assert elapsed <= 0.5
    assert persisted_paths == [existing]


def test_cli_multi_root_live_update_stays_root_scoped_after_cli_index(
    cli_runner,
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha.txt").write_text("alpha baseline marker\n", encoding="utf-8")

    index_result = cli_runner(
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
        "--rebuild",
    )
    assert index_result.returncode == 0

    conn = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root_a)
        service.start(root_b)

        created = root_b / "beta-live.txt"
        created.write_text("beta scoped cli live update\n", encoding="utf-8")
        elapsed = _wait_for_cli_hit(
            cli_runner,
            db_path,
            service,
            writer,
            "beta scoped cli live update",
            created,
            root=root_b,
        )
        alpha_paths = _search_paths(cli_runner, db_path, "beta scoped cli live update", root=root_a)
        beta_paths = _search_paths(cli_runner, db_path, "beta scoped cli live update", root=root_b)
    finally:
        service.stop()
        conn.close()

    assert elapsed <= 0.5
    assert alpha_paths == []
    assert beta_paths == [created]
