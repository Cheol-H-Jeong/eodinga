from __future__ import annotations

from pathlib import Path

from eodinga.index.storage import connect_database, temporary_pragmas


def test_temporary_pragmas_skips_redundant_pragma_writes(tmp_path: Path) -> None:
    conn = connect_database(tmp_path / "index.db")
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        with temporary_pragmas(conn, {"synchronous": "FULL", "cache_size": -64000}):
            pass
    finally:
        conn.set_trace_callback(None)
        conn.close()

    assert "PRAGMA synchronous=FULL;" not in statements
    assert "PRAGMA cache_size=-64000;" not in statements
    assert "PRAGMA synchronous=2;" not in statements
    assert "PRAGMA cache_size=-64000;" not in statements
