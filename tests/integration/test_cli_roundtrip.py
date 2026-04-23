from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [sys.executable, "-m", "eodinga", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_multi_root_search_scope_survives_reopen_across_processes(tmp_path: Path) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha-shared.txt").write_text("shared process scope\n", encoding="utf-8")
    (root_b / "beta-shared.txt").write_text("shared process scope\n", encoding="utf-8")

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
    global_search = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "search",
        "shared process scope",
        "--json",
    )
    scoped_search = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "search",
        "shared process scope",
        "--json",
        "--root",
        str(root_b),
    )

    assert index_result.returncode == 0
    global_payload = json.loads(global_search.stdout)
    scoped_payload = json.loads(scoped_search.stdout)
    assert {Path(item["path"]) for item in global_payload["results"]} == {
        root_a / "alpha-shared.txt",
        root_b / "beta-shared.txt",
    }
    assert [Path(item["path"]) for item in scoped_payload["results"]] == [
        root_b / "beta-shared.txt"
    ]


def test_cli_rebuild_replaces_searchable_snapshot_for_next_process(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "index.db"
    root.mkdir()
    before = root / "before.txt"
    after = root / "after.txt"
    before.write_text("process rebuild before\n", encoding="utf-8")

    first_index = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    first_search = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "search",
        "process rebuild before",
        "--json",
    )

    before.unlink()
    after.write_text("process rebuild after\n", encoding="utf-8")

    second_index = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    old_search = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "search",
        "process rebuild before",
        "--json",
    )
    new_search = _run_cli(
        tmp_path,
        "--db",
        str(db_path),
        "search",
        "process rebuild after",
        "--json",
    )

    assert first_index.returncode == 0
    assert second_index.returncode == 0
    first_payload = json.loads(first_search.stdout)
    old_payload = json.loads(old_search.stdout)
    new_payload = json.loads(new_search.stdout)
    assert [Path(item["path"]) for item in first_payload["results"]] == [before]
    assert old_payload["results"] == []
    assert [Path(item["path"]) for item in new_payload["results"]] == [after]
