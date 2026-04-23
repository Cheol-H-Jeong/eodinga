from __future__ import annotations

import signal
import sqlite3
from pathlib import Path
from typing import cast

import pytest

import eodinga.index.build as build_module
from eodinga.config import RootConfig
from eodinga.index.build import rebuild_index
from eodinga.index.schema import apply_schema
from eodinga.observability import reset_metrics, snapshot_metrics


def test_rebuild_index_failure_keeps_existing_target_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "fresh.txt").write_text("fresh content\n", encoding="utf-8")

    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(tmp_path / "existing-root"), "[]", "[]", 1),
        )
        conn.execute(
            """
            INSERT INTO files (
              id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
              is_dir, is_symlink, content_hash, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "/existing/live.txt",
                "/existing",
                "live.txt",
                "live.txt",
                "txt",
                4,
                1,
                1,
                0,
                0,
                None,
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    original_walk_batched = build_module.walk_batched

    def failing_walk_batched(root_path: Path, rules, root_id: int = 0):
        yield from original_walk_batched(root_path, rules, root_id=root_id)
        raise RuntimeError("simulated rebuild failure")

    monkeypatch.setattr(build_module, "walk_batched", failing_walk_batched)

    with pytest.raises(RuntimeError, match="simulated rebuild failure"):
        rebuild_index(db_path, [RootConfig(path=root)])

    reopened = sqlite3.connect(db_path)
    try:
        rows = reopened.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == ["/existing/live.txt"]
    finally:
        reopened.close()

    staged_path = db_path.with_name(".index.db.next")
    assert not staged_path.exists()
    assert not staged_path.with_name(".index.db.next-wal").exists()


def test_rebuild_index_records_runtime_metrics(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (root / "beta.txt").write_text("beta\n", encoding="utf-8")
    db_path = tmp_path / "index.db"
    reset_metrics()

    result = rebuild_index(db_path, [RootConfig(path=root)], content_enabled=False)

    metrics = snapshot_metrics()
    batch_histogram = cast(dict[str, object], metrics["histograms"]["index_batch_size"])
    assert result.files_indexed == 3
    assert metrics["counters"]["index_rebuilds_completed"] == 1
    assert metrics["counters"]["files_indexed"] == 3
    assert metrics["histograms"]["index_rebuild_latency_ms"]["count"] == 1
    assert cast(int, batch_histogram["count"]) >= 1


def test_rebuild_index_interrupt_preserves_staged_database_for_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (root / "beta.txt").write_text("beta\n", encoding="utf-8")
    db_path = tmp_path / "index.db"
    staged_path = db_path.with_name(".index.db.next")

    original_walk_batched = build_module.walk_batched

    def interrupting_walk_batched(root_path: Path, rules, root_id: int = 0):
        yielded_first = False
        for batch in original_walk_batched(root_path, rules, root_id=root_id):
            yield batch
            if not yielded_first:
                yielded_first = True
                stop = current_stop
                assert stop is not None
                stop._handle_signal(signal.SIGTERM, None)

    current_stop: build_module._SignalStop | None = None
    original_enter = build_module._SignalStop.__enter__

    def recording_enter(self: build_module._SignalStop) -> build_module._SignalStop:
        nonlocal current_stop
        current_stop = self
        return original_enter(self)

    monkeypatch.setattr(build_module, "walk_batched", interrupting_walk_batched)
    monkeypatch.setattr(build_module._SignalStop, "__enter__", recording_enter)

    with pytest.raises(KeyboardInterrupt):
        rebuild_index(db_path, [RootConfig(path=root)], content_enabled=False)

    assert staged_path.exists()
    resumed = sqlite3.connect(staged_path)
    try:
        rows = resumed.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == [
            str(root),
            str(root / "alpha.txt"),
            str(root / "beta.txt"),
        ]
    finally:
        resumed.close()


def test_rebuild_index_raises_after_finishing_swap_when_signal_arrives_during_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    db_path = tmp_path / "index.db"

    current_stop: build_module._SignalStop | None = None
    original_enter = build_module._SignalStop.__enter__
    original_atomic_replace = build_module.atomic_replace_index

    def recording_enter(self: build_module._SignalStop) -> build_module._SignalStop:
        nonlocal current_stop
        current_stop = self
        return original_enter(self)

    def signal_after_swap(staged_path: Path, target_path: Path) -> None:
        original_atomic_replace(staged_path, target_path)
        stop = current_stop
        assert stop is not None
        stop._handle_signal(signal.SIGTERM, None)

    monkeypatch.setattr(build_module._SignalStop, "__enter__", recording_enter)
    monkeypatch.setattr(build_module, "atomic_replace_index", signal_after_swap)

    with pytest.raises(KeyboardInterrupt):
        rebuild_index(db_path, [RootConfig(path=root)], content_enabled=False)

    reopened = sqlite3.connect(db_path)
    try:
        rows = reopened.execute("SELECT path FROM files ORDER BY path").fetchall()
        assert [str(row[0]) for row in rows] == [str(root), str(root / "alpha.txt")]
    finally:
        reopened.close()

    staged_path = db_path.with_name(".index.db.next")
    assert not staged_path.exists()
    assert not staged_path.with_name(".index.db.next-wal").exists()


def test_rebuild_index_installs_sigint_and_sigterm_handlers_on_main_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed: list[signal.Signals] = []
    restored: list[signal.Signals] = []
    previous_handlers: dict[signal.Signals, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }

    def fake_getsignal(signum: signal.Signals) -> object:
        return previous_handlers[signum]

    def fake_signal(signum: signal.Signals, handler: object) -> object:
        if handler in previous_handlers.values():
            restored.append(signum)
        else:
            installed.append(signum)
        return handler

    monkeypatch.setattr(build_module.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(build_module.signal, "signal", fake_signal)

    with build_module._SignalStop():
        pass

    assert installed == [signal.SIGINT, signal.SIGTERM]
    assert restored == [signal.SIGINT, signal.SIGTERM]


def test_signal_stop_restores_installed_handlers_if_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_handlers: dict[signal.Signals, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    installed: list[signal.Signals] = []
    restored: list[signal.Signals] = []

    def fake_getsignal(signum: signal.Signals) -> object:
        return previous_handlers[signum]

    def fake_signal(signum: signal.Signals, handler: object) -> object:
        if signum == signal.SIGTERM and handler == stop._handle_signal:
            raise RuntimeError("simulated signal install failure")
        if handler == stop._handle_signal:
            installed.append(signum)
        elif handler == previous_handlers[signum]:
            restored.append(signum)
        return handler

    monkeypatch.setattr(build_module.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(build_module.signal, "signal", fake_signal)

    stop = build_module._SignalStop()

    with pytest.raises(RuntimeError, match="simulated signal install failure"):
        stop.__enter__()

    assert installed == [signal.SIGINT]
    assert restored == [signal.SIGINT]
    assert stop._active is False


def test_signal_stop_raises_pending_signal_on_context_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_handlers: dict[signal.Signals, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    restored: list[signal.Signals] = []
    stop = build_module._SignalStop()

    def fake_getsignal(signum: signal.Signals) -> object:
        return previous_handlers[signum]

    def fake_signal(signum: signal.Signals, handler: object) -> object:
        if handler == previous_handlers[signum]:
            restored.append(signum)
        return handler

    monkeypatch.setattr(build_module.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(build_module.signal, "signal", fake_signal)

    with pytest.raises(KeyboardInterrupt):
        with stop:
            stop._handle_signal(signal.SIGTERM, None)

    assert restored == [signal.SIGINT, signal.SIGTERM]
    assert stop._active is False
    assert stop._handlers == {}


def test_signal_stop_does_not_replace_existing_exception_with_pending_signal() -> None:
    stop = build_module._SignalStop()
    stop._active = True
    stop._handlers = {}
    stop._handle_signal(signal.SIGINT, None)

    result = stop.__exit__(RuntimeError, RuntimeError("boom"), None)

    assert result is False
