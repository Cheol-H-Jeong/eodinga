from __future__ import annotations

import json
from pathlib import Path


def _json_payload(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


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
