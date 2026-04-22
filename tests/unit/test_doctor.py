from __future__ import annotations

from pathlib import Path

from eodinga.config import AppConfig, RootConfig
from eodinga.doctor import run_diagnostics


def test_doctor_returns_expected_shape(tmp_path: Path) -> None:
    config = AppConfig(roots=[RootConfig(path=tmp_path)])
    report, exit_code = run_diagnostics(config=config, db_path=tmp_path / "index.db")
    assert exit_code == 0
    assert set(report) == {"python", "dependencies", "db", "roots", "hotkey_backend", "default_excludes"}
    assert report["default_excludes"]["effective"] is True


def test_doctor_flags_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    from eodinga import doctor

    monkeypatch.setattr(doctor, "_is_importable", lambda name: name != "pydantic")
    report, exit_code = run_diagnostics(config=AppConfig(), db_path=tmp_path / "index.db")
    assert exit_code == 1
    assert report["dependencies"]["required"]["pydantic"] is False
