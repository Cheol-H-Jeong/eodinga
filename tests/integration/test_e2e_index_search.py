from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.common import PathRules
from eodinga.content.registry import parse
from eodinga.index import open_index
from eodinga.index.writer import IndexWriter
from eodinga.core.walker import walk_batched
from eodinga.query import search


def _build_fixture_tree(root: Path) -> None:
    files = {
        "docs/launch-plan.md": "# Launch Plan\nAlpha launch checklist for spring release.\n",
        "docs/invoice-budget.txt": "Invoice budget for the alpha launch.\n",
        "archive/retro-notes.txt": "Archive retrospective notes from last quarter.\n",
        "src/hot_restart.py": "def reopen_index():\n    return 'restart ready'\n",
        "src/watch_coalesce.py": "EVENT_NAME = 'coalesce'\n",
        "korean/회의록-봄.txt": "봄 프로젝트 회의록과 실행 항목.\n",
        "korean/영수증-정산.txt": "정산 영수증과 비용 내역.\n",
    }
    for relative_path, body in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def _index_tree(root: Path, db_path: Path) -> None:
    conn = open_index(db_path)
    try:
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(root), "[]", "[]", 1),
        )
        conn.commit()
        writer = IndexWriter(conn, parser_callback=lambda path: parse(path, max_body_chars=4096))
        rules = PathRules(root=root, include=(str(root), f"{root}/**"), exclude=())
        records = [
            record
            for batch in walk_batched(root, rules, root_id=1)
            for record in batch
        ]
        assert writer.bulk_upsert(records) == len(records)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("launch-plan", "launch-plan.md"),
        ('content:"launch checklist"', "launch-plan.md"),
        ("ext:md launch", "launch-plan.md"),
        ("path:archive retro", "retro-notes.txt"),
        ("path:src reopen_index", "hot_restart.py"),
        ("content:/coalesce/i", "watch_coalesce.py"),
        ("회의록", "회의록-봄.txt"),
        ("content:정산", "영수증-정산.txt"),
        ("path:korean 영수증", "영수증-정산.txt"),
        ("invoice budget", "invoice-budget.txt"),
    ],
)
def test_e2e_index_search_returns_expected_file_in_top_three(
    tmp_path: Path, query: str, expected_name: str
) -> None:
    root = tmp_path / "workspace"
    db_path = tmp_path / "database" / "index.db"
    _build_fixture_tree(root)
    _index_tree(root, db_path)

    conn = open_index(db_path)
    try:
        hits = [hit.file.name for hit in search(conn, query, limit=3).hits]
    finally:
        conn.close()

    assert expected_name in hits
