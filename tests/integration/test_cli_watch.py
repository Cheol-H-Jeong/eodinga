from __future__ import annotations

import json
import os
import select
import signal
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from time import monotonic

from eodinga.config import AppConfig, IndexConfig, RootConfig
from eodinga.index.storage import configure_connection
from eodinga.query import search


def _write_config(config_path: Path, db_path: Path, roots: list[Path]) -> None:
    AppConfig(
        index=IndexConfig(db_path=db_path),
        roots=[RootConfig(path=root) for root in roots],
    ).save(config_path)


def _run_cli(config_path: Path, db_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [sys.executable, "-m", "eodinga", "--config", str(config_path), "--db", str(db_path), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _start_watch(config_path: Path, db_path: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.Popen(
        [sys.executable, "-m", "eodinga", "--config", str(config_path), "--db", str(db_path), "watch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )


def _wait_for_watch_ready(process: subprocess.Popen[str], *, timeout: float = 5.0) -> dict[str, object]:
    assert process.stdout is not None
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if process.poll() is not None:
            stderr = "" if process.stderr is None else process.stderr.read()
            raise AssertionError(f"watch exited early: {stderr}")
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if not ready:
            continue
        line = process.stdout.readline()
        if not line:
            continue
        return json.loads(line)
    raise AssertionError("watch did not report readiness")


def _wait_for_search_hit(
    db_path: Path,
    query: str,
    expected_path: Path,
    *,
    timeout: float = 0.5,
    root: Path | None = None,
) -> float:
    started = monotonic()
    deadline = started + timeout
    while monotonic() < deadline:
        with closing(configure_connection(sqlite3.connect(db_path))) as conn:
            hits = [hit.file.path for hit in search(conn, query, limit=5, root=root).hits]
        if expected_path in hits:
            return monotonic() - started
    raise AssertionError(f"{expected_path} did not become query-visible within {timeout:.3f}s")


def _stop_watch(process: subprocess.Popen[str]) -> subprocess.CompletedProcess[str]:
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate(timeout=5)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def test_watch_cli_indexes_live_update_visible_to_search_within_500ms(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    config_path = tmp_path / "config.toml"
    db_path = tmp_path / "index.db"
    root.mkdir()
    (root / "existing.txt").write_text("existing watch note\n", encoding="utf-8")
    _write_config(config_path, db_path, [root])

    indexed = _run_cli(config_path, db_path, "index")
    assert indexed.returncode == 0, indexed.stderr

    process = _start_watch(config_path, db_path)
    try:
        ready = _wait_for_watch_ready(process)
        created = root / "live-watch.txt"
        created.write_text("cli watch live update\n", encoding="utf-8")
        elapsed = _wait_for_search_hit(db_path, "cli watch live update", created)
    finally:
        stopped = _stop_watch(process)

    assert ready["status"] == "watching"
    assert ready["roots"] == [str(root)]
    assert stopped.returncode == 0, stopped.stderr
    assert elapsed <= 0.5


def test_watch_cli_multi_root_updates_global_and_root_scoped_search(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    config_path = tmp_path / "config.toml"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha.txt").write_text("alpha steady state\n", encoding="utf-8")
    _write_config(config_path, db_path, [root_a, root_b])

    indexed = _run_cli(config_path, db_path, "index")
    assert indexed.returncode == 0, indexed.stderr

    process = _start_watch(config_path, db_path)
    try:
        _wait_for_watch_ready(process)
        created = root_b / "beta-live.txt"
        created.write_text("beta cli scoped update\n", encoding="utf-8")
        elapsed = _wait_for_search_hit(db_path, "beta cli scoped update", created, timeout=1.0)
        with closing(configure_connection(sqlite3.connect(db_path))) as conn:
            global_hits = [hit.file.path for hit in search(conn, "beta cli scoped update", limit=5).hits]
            alpha_hits = [
                hit.file.path
                for hit in search(conn, "beta cli scoped update", limit=5, root=root_a).hits
            ]
            beta_hits = [
                hit.file.path
                for hit in search(conn, "beta cli scoped update", limit=5, root=root_b).hits
            ]
    finally:
        stopped = _stop_watch(process)

    assert stopped.returncode == 0, stopped.stderr
    assert elapsed <= 1.0
    assert global_hits == [created]
    assert alpha_hits == []
    assert beta_hits == [created]
