from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic

from eodinga.config import AppConfig, IndexConfig, RootConfig
from eodinga.index import open_index
from eodinga.query import search


def _write_config(config_path: Path, db_path: Path, roots: list[Path]) -> None:
    AppConfig(
        index=IndexConfig(db_path=db_path),
        roots=[RootConfig(path=root) for root in roots],
    ).save(config_path)


def _run_cli(config_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [sys.executable, "-m", "eodinga", "--config", str(config_path), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _start_watch(config_path: Path) -> tuple[subprocess.Popen[str], dict[str, object]]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    process = subprocess.Popen(
        [sys.executable, "-m", "eodinga", "--config", str(config_path), "watch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert process.stdout is not None
    payload_line = process.stdout.readline().strip()
    assert payload_line
    return process, json.loads(payload_line)


def _stop_watch(process: subprocess.Popen[str]) -> subprocess.CompletedProcess[str]:
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate(timeout=5)
    return subprocess.CompletedProcess(
        args=process.args,
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _wait_for_query_hit(db_path: Path, query: str, expected_path: Path, deadline_seconds: float) -> float:
    started = monotonic()
    deadline = started + deadline_seconds
    while monotonic() < deadline:
        hits = _search_hits(db_path, query)
        if expected_path in hits:
            return monotonic() - started
    raise AssertionError(f"{expected_path} did not become query-visible within {deadline_seconds:.3f}s")


def _search_hits(db_path: Path, query: str, *, root: Path | None = None) -> list[Path]:
    conn = open_index(db_path)
    try:
        return [hit.file.path for hit in search(conn, query, limit=5, root=root).hits]
    finally:
        conn.close()


def test_watch_cli_keeps_index_queryable_and_refreshes_live_updates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    config_path = tmp_path / "config.toml"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted before watch\n", encoding="utf-8")
    _write_config(config_path, db_path, [root])

    index_result = _run_cli(config_path, "index", "--rebuild")
    initial_search = _run_cli(config_path, "search", "persisted before watch", "--json")

    process, payload = _start_watch(config_path)
    try:
        created = root / "created-after-watch.txt"
        created.write_text("watch subprocess live update\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            db_path,
            "watch subprocess live update",
            created,
            deadline_seconds=0.5,
        )
    finally:
        stopped = _stop_watch(process)

    assert index_result.returncode == 0, index_result.stderr
    assert initial_search.returncode == 0, initial_search.stderr
    assert json.loads(initial_search.stdout)["returned"] == 1
    assert payload["command"] == "watch"
    assert payload["db"] == str(db_path)
    assert elapsed <= 0.5
    assert stopped.returncode == 130, stopped.stderr


def test_watch_cli_multi_root_updates_respect_root_scope(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    config_path = tmp_path / "config.toml"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha.txt").write_text("alpha baseline content\n", encoding="utf-8")
    _write_config(config_path, db_path, [root_a, root_b])

    index_result = _run_cli(config_path, "index", "--rebuild")

    process, payload = _start_watch(config_path)
    try:
        created = root_b / "beta-live.txt"
        created.write_text("beta scoped subprocess update\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            db_path,
            "beta scoped subprocess update",
            created,
            deadline_seconds=1.5,
        )
        alpha_hits = _search_hits(db_path, "beta scoped subprocess update", root=root_a)
        beta_hits = _search_hits(db_path, "beta scoped subprocess update", root=root_b)
    finally:
        stopped = _stop_watch(process)

    assert index_result.returncode == 0, index_result.stderr
    assert payload["roots"] == [str(root_a), str(root_b)]
    assert elapsed <= 1.5
    assert alpha_hits == []
    assert beta_hits == [created]
    assert stopped.returncode == 130, stopped.stderr


def test_watch_cli_restart_preserves_existing_queries_and_accepts_new_updates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    config_path = tmp_path / "config.toml"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted restart baseline\n", encoding="utf-8")
    _write_config(config_path, db_path, [root])

    index_result = _run_cli(config_path, "index", "--rebuild")

    first_process, _ = _start_watch(config_path)
    first_stop = _stop_watch(first_process)

    second_process, _ = _start_watch(config_path)
    try:
        created = root / "after-restart.txt"
        created.write_text("watch restart follow up\n", encoding="utf-8")
        elapsed = _wait_for_query_hit(
            db_path,
            "watch restart follow up",
            created,
            deadline_seconds=1.5,
        )
        persisted_hits = _search_hits(db_path, "persisted restart baseline")
    finally:
        second_stop = _stop_watch(second_process)

    assert index_result.returncode == 0, index_result.stderr
    assert first_stop.returncode == 130, first_stop.stderr
    assert elapsed <= 1.5
    assert persisted_hits == [existing]
    assert second_stop.returncode == 130, second_stop.stderr
