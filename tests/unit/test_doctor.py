from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from eodinga.config import AppConfig, RootConfig
from eodinga.doctor import run_diagnostics
from eodinga.index.storage import mark_build_stage_complete
from eodinga.index.schema import apply_schema


def test_doctor_returns_expected_shape(tmp_path: Path) -> None:
    config = AppConfig(roots=[RootConfig(path=tmp_path)])
    report, exit_code = run_diagnostics(config=config, db_path=tmp_path / "index.db")
    assert exit_code == 0
    assert set(report) == {"python", "dependencies", "db", "roots", "hotkey_backend", "default_excludes"}
    assert report["default_excludes"]["effective"] is True
    assert report["db"]["exists"] is False
    assert report["db"]["interrupted_build_resumed"] is False
    assert report["db"]["interrupted_recovery_resumed"] is False
    assert report["db"]["stale_wal_present"] is False
    assert report["db"]["stale_wal_recovered"] is False
    assert report["db"]["stale_wal_error"] is None


def test_doctor_flags_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    from eodinga import doctor

    monkeypatch.setattr(doctor, "_is_importable", lambda name: name != "pydantic")
    report, exit_code = run_diagnostics(config=AppConfig(), db_path=tmp_path / "index.db")
    assert exit_code == 1
    assert report["dependencies"]["required"]["pydantic"] is False


def test_doctor_recovers_stale_wal_before_reporting(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    db_path = tmp_path / "index.db"

    conn = sqlite3.connect(source)
    apply_schema(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0;")
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    conn.commit()

    shutil.copy2(source, db_path)
    shutil.copy2(source.with_name("source.db-wal"), db_path.with_name("index.db-wal"))
    shutil.copy2(source.with_name("source.db-shm"), db_path.with_name("index.db-shm"))
    conn.close()

    report, exit_code = run_diagnostics(config=AppConfig(), db_path=db_path)

    assert exit_code == 0
    assert report["db"]["exists"] is True
    assert report["db"]["interrupted_build_resumed"] is False
    assert report["db"]["interrupted_recovery_resumed"] is False
    assert report["db"]["stale_wal_present"] is True
    assert report["db"]["stale_wal_recovered"] is True
    assert report["db"]["stale_wal_error"] is None
    wal_path = db_path.with_name("index.db-wal")
    assert not wal_path.exists() or wal_path.stat().st_size == 0


def test_doctor_fails_when_stale_wal_recovery_fails(monkeypatch, tmp_path: Path) -> None:
    from eodinga import doctor

    db_path = tmp_path / "index.db"
    db_path.write_bytes(b"sqlite")

    monkeypatch.setattr(doctor, "has_stale_wal", lambda _path: True)
    monkeypatch.setattr(doctor, "recover_stale_wal", lambda _path: False)

    report, exit_code = run_diagnostics(config=AppConfig(), db_path=db_path)

    assert exit_code == 1
    assert report["db"]["stale_wal_present"] is True
    assert report["db"]["stale_wal_recovered"] is False
    assert report["db"]["stale_wal_error"] == f"failed to recover stale WAL for {db_path}"


def test_doctor_resumes_interrupted_recovery_before_reporting(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    staged_path = tmp_path / ".index.db.recover"

    conn = sqlite3.connect(staged_path)
    apply_schema(conn)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    conn.commit()
    conn.close()

    report, exit_code = run_diagnostics(config=AppConfig(), db_path=db_path)

    assert exit_code == 0
    assert report["db"]["exists"] is True
    assert report["db"]["interrupted_build_resumed"] is False
    assert report["db"]["interrupted_recovery_resumed"] is True
    assert report["db"]["stale_wal_present"] is False
    assert report["db"]["stale_wal_recovered"] is False
    assert report["db"]["stale_wal_error"] is None
    assert not staged_path.exists()


def test_doctor_resumes_interrupted_build_before_reporting(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    staged_path = tmp_path / ".index.db.next"

    conn = sqlite3.connect(staged_path)
    apply_schema(conn)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        (str(tmp_path), "[]", "[]", 1),
    )
    conn.commit()
    conn.close()
    mark_build_stage_complete(staged_path)

    report, exit_code = run_diagnostics(config=AppConfig(), db_path=db_path)

    assert exit_code == 0
    assert report["db"]["exists"] is True
    assert report["db"]["interrupted_build_resumed"] is True
    assert report["db"]["interrupted_recovery_resumed"] is False
    assert report["db"]["stale_wal_present"] is False
    assert report["db"]["stale_wal_recovered"] is False
    assert report["db"]["stale_wal_error"] is None
    assert not staged_path.exists()


def test_doctor_discards_incomplete_interrupted_build_before_reporting(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    staged_path = tmp_path / ".index.db.next"

    conn = sqlite3.connect(staged_path)
    apply_schema(conn)
    conn.execute(
        "INSERT INTO roots(path, include, exclude, added_at) VALUES (?, ?, ?, ?)",
        ("/partial", "[]", "[]", 1),
    )
    conn.commit()
    conn.close()

    report, exit_code = run_diagnostics(config=AppConfig(), db_path=db_path)

    assert exit_code == 0
    assert report["db"]["exists"] is False
    assert report["db"]["interrupted_build_resumed"] is False
    assert not staged_path.exists()
