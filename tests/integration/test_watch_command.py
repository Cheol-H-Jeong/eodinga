from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep


def _cli_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    env["XDG_DATA_HOME"] = str(tmp_path / ".local-share")
    return env


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "eodinga", *args],
        cwd=tmp_path,
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )


def _spawn_watch(tmp_path: Path, db_path: Path) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {}
    if sys.platform.startswith("win") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [sys.executable, "-m", "eodinga", "--db", str(db_path), "watch"],
        cwd=tmp_path,
        env=_cli_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )


def _wait_for_watch_ready(process: subprocess.Popen[str], *, deadline_seconds: float = 1.0) -> None:
    deadline = monotonic() + deadline_seconds
    while monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                f"watch exited before becoming ready: returncode={process.returncode} "
                f"stdout={stdout!r} stderr={stderr!r}"
            )
        sleep(0.05)


def _stop_watch(process: subprocess.Popen[str]) -> tuple[int, str, str]:
    if process.poll() is None:
        if sys.platform.startswith("win") and hasattr(signal, "CTRL_BREAK_EVENT"):
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate(timeout=5)
    return int(process.returncode), stdout, stderr


def _wait_for_search_paths(
    tmp_path: Path,
    db_path: Path,
    query: str,
    expected_paths: set[Path],
    *,
    root: Path | None = None,
    deadline_seconds: float = 2.0,
) -> set[Path]:
    deadline = monotonic() + deadline_seconds
    last_result: subprocess.CompletedProcess[str] | None = None
    while monotonic() < deadline:
        args = ["--db", str(db_path), "search", query, "--json"]
        if root is not None:
            args.extend(["--root", str(root)])
        last_result = _run_cli(tmp_path, *args)
        if last_result.returncode == 0:
            payload = json.loads(last_result.stdout)
            paths = {Path(item["path"]) for item in payload["results"]}
            if paths == expected_paths:
                return paths
        sleep(0.05)
    details = ""
    if last_result is not None:
        details = f" last stdout={last_result.stdout!r} stderr={last_result.stderr!r}"
    raise AssertionError(
        f"query {query!r} did not converge to {expected_paths!r} within {deadline_seconds:.2f}s.{details}"
    )


def test_watch_command_persists_live_updates_across_process_restart(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted baseline query\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    index_result = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    assert index_result.returncode == 0, index_result.stderr

    watch = _spawn_watch(tmp_path, db_path)
    try:
        _wait_for_watch_ready(watch)
        sleep(0.5)
        created = root / "live-note.txt"
        created.write_text("post watch persistence\n", encoding="utf-8")
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "post watch persistence",
            {created},
        ) == {created}
    finally:
        return_code, _, stderr = _stop_watch(watch)

    assert return_code != 0, stderr
    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "post watch persistence",
        {root / "live-note.txt"},
    ) == {root / "live-note.txt"}

    restarted = _spawn_watch(tmp_path, db_path)
    try:
        _wait_for_watch_ready(restarted)
        sleep(0.5)
        rewritten = root / "live-note.txt"
        rewritten.write_text("post restart rewrite\n", encoding="utf-8")
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "post restart rewrite",
            {rewritten},
        ) == {rewritten}
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "post watch persistence",
            set(),
        ) == set()
    finally:
        _stop_watch(restarted)

    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "post restart rewrite",
        {root / "live-note.txt"},
    ) == {root / "live-note.txt"}


def test_watch_command_keeps_multi_root_live_updates_scoped_after_restart(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    root_a.mkdir()
    root_b.mkdir()
    survivor = root_a / "alpha.txt"
    survivor.write_text("alpha scoped baseline\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    index_result = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
        "--rebuild",
    )
    assert index_result.returncode == 0, index_result.stderr

    watch = _spawn_watch(tmp_path, db_path)
    try:
        _wait_for_watch_ready(watch)
        sleep(0.5)
        destination = root_b / "created.txt"
        destination.write_text("cli scoped beta creation\n", encoding="utf-8")
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "cli scoped beta creation",
            {destination},
        ) == {destination}
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "cli scoped beta creation",
            set(),
            root=root_a,
        ) == set()
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "cli scoped beta creation",
            {destination},
            root=root_b,
        ) == {destination}
        assert _wait_for_search_paths(
            tmp_path,
            db_path,
            "alpha scoped baseline",
            {survivor},
            root=root_a,
        ) == {survivor}
    finally:
        _stop_watch(watch)

    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "cli scoped beta creation",
        {destination},
    ) == {destination}
    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "cli scoped beta creation",
        set(),
        root=root_a,
    ) == set()
    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "cli scoped beta creation",
        {destination},
        root=root_b,
    ) == {destination}
    assert _wait_for_search_paths(
        tmp_path,
        db_path,
        "alpha scoped baseline",
        {survivor},
        root=root_a,
    ) == {survivor}
