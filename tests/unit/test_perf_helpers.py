from __future__ import annotations

from pathlib import Path

import pytest

from tests.perf._helpers import open_perf_db, perf_float_env, perf_int_env


def test_perf_int_env_uses_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EODINGA_PERF_QUERY_COUNT", raising=False)

    assert perf_int_env("EODINGA_PERF_QUERY_COUNT", 2000) == 2000


def test_perf_int_env_rejects_non_positive_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODINGA_PERF_QUERY_COUNT", "0")

    with pytest.raises(ValueError, match="must be > 0"):
        perf_int_env("EODINGA_PERF_QUERY_COUNT", 2000)


def test_perf_float_env_reads_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODINGA_PERF_QUERY_P95_MS", "45.5")

    assert perf_float_env("EODINGA_PERF_QUERY_P95_MS", 30.0) == 45.5


@pytest.mark.parametrize(("bulk_writes", "expected"), [(False, 2), (True, 1)])
def test_open_perf_db_applies_requested_write_profile(tmp_path: Path, bulk_writes: bool, expected: int) -> None:
    conn = open_perf_db(tmp_path / "perf.db", bulk_writes=bulk_writes)
    try:
        pragma = conn.execute("PRAGMA synchronous;").fetchone()
        assert pragma is not None
        assert int(pragma[0]) == expected
    finally:
        conn.close()
