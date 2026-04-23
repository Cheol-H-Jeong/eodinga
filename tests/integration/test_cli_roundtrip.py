from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from eodinga.__main__ import main
from eodinga.content.registry import parse
from eodinga.core.watcher import WatchService
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from tests.integration._helpers import wait_for_query_hit


def _run_json(capsys, *args: str) -> tuple[dict[str, Any], str]:
    exit_code = main(list(args))
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = cast(dict[str, Any], json.loads(captured.out))
    return payload, captured.err


def _result_paths(payload: dict[str, Any]) -> list[Path]:
    return [Path(item["path"]) for item in cast(list[dict[str, Any]], payload["results"])]


def test_cli_index_search_and_stats_roundtrip_with_real_filesystem(
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    alpha = root / "alpha-launch.txt"
    beta = root / "beta-notes.txt"
    alpha.write_text("launch agenda and shipping notes\n", encoding="utf-8")
    beta.write_text("engineering notes only\n", encoding="utf-8")

    index_payload, index_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root),
        "--rebuild",
    )
    search_payload, search_err = _run_json(capsys, "--db", str(db_path), "search", "launch agenda", "--json")
    stats_payload, stats_err = _run_json(capsys, "--db", str(db_path), "stats", "--json")

    assert index_err == ""
    assert search_err == ""
    assert stats_err == ""
    assert index_payload["files_indexed"] >= 2
    assert index_payload["roots"] == [str(root)]
    assert _result_paths(search_payload) == [alpha]
    assert search_payload["count"] == 1
    assert stats_payload["files_indexed"] == index_payload["files_indexed"]
    assert stats_payload["documents_indexed"] == 2
    assert Path(stats_payload["db_path"]) == db_path
    assert Path(stats_payload["roots"][0]) == root


def test_cli_multi_root_search_scope_persists_across_separate_commands(
    tmp_path: Path,
    capsys,
) -> None:
    root_a = tmp_path / "alpha-root"
    root_b = tmp_path / "beta-root"
    db_path = tmp_path / "database" / "index.db"
    root_a.mkdir()
    root_b.mkdir()
    alpha = root_a / "alpha-plan.txt"
    beta = root_b / "beta-plan.txt"
    alpha.write_text("shared roadmap alpha only\n", encoding="utf-8")
    beta.write_text("shared roadmap beta only\n", encoding="utf-8")

    _, index_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "index",
        "--root",
        str(root_a),
        "--root",
        str(root_b),
        "--rebuild",
    )
    all_payload, all_err = _run_json(capsys, "--db", str(db_path), "search", "shared roadmap", "--json")
    alpha_payload, alpha_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "search",
        "shared roadmap",
        "--json",
        "--root",
        str(root_a),
    )
    beta_payload, beta_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "search",
        "shared roadmap",
        "--json",
        "--root",
        str(root_b),
    )

    assert index_err == ""
    assert all_err == ""
    assert alpha_err == ""
    assert beta_err == ""
    assert set(_result_paths(all_payload)) == {alpha, beta}
    assert _result_paths(alpha_payload) == [alpha]
    assert _result_paths(beta_payload) == [beta]


def test_cli_reopen_then_live_update_is_visible_to_followup_search(
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text("persisted restart marker\n", encoding="utf-8")

    _, index_err = _run_json(capsys, "--db", str(db_path), "index", "--root", str(root), "--rebuild")
    initial_payload, initial_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "search",
        "persisted restart",
        "--json",
    )

    reopened = open_index(db_path)
    service = WatchService()
    try:
        writer = IndexWriter(reopened, parser_callback=lambda path: parse(path, max_body_chars=2048))
        service.start(root)

        created = root / "after-reopen.txt"
        created.write_text("live update after reopen\n", encoding="utf-8")
        elapsed = wait_for_query_hit(
            reopened,
            service,
            writer,
            "live update after reopen",
            created,
            deadline_seconds=0.5,
        )
    finally:
        service.stop()
        reopened.close()

    followup_payload, followup_err = _run_json(
        capsys,
        "--db",
        str(db_path),
        "search",
        "live update after reopen",
        "--json",
    )

    assert index_err == ""
    assert initial_err == ""
    assert followup_err == ""
    assert _result_paths(initial_payload) == [existing]
    assert elapsed <= 0.5
    assert _result_paths(followup_payload) == [created]
