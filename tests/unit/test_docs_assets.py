from __future__ import annotations

from pathlib import Path

from eodinga.gui.docs import render_doc_screenshots


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_render_doc_screenshots_writes_expected_assets(tmp_path: Path, qapp) -> None:
    app_path, launcher_path = render_doc_screenshots(tmp_path)

    assert app_path.name == "app-window.png"
    assert launcher_path.name == "launcher-window.png"
    assert app_path.exists()
    assert launcher_path.exists()
    assert app_path.stat().st_size > 0
    assert launcher_path.stat().st_size > 0


def test_docs_reference_expected_assets_and_guides() -> None:
    root = _repo_root()
    readme = (root / "README.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    dsl = (root / "docs" / "DSL.md").read_text(encoding="utf-8")
    performance = (root / "docs" / "PERFORMANCE.md").read_text(encoding="utf-8")

    assert "![Main application window]" in readme
    assert "![Launcher window]" in readme
    assert "## Install" in readme
    assert "## Hotkey" in readme
    assert "## Limitations" in readme
    assert "docs/DSL.md" in readme
    assert "docs/ARCHITECTURE.md" in readme
    assert "docs/PERFORMANCE.md" in readme

    assert "## Runtime Flow" in architecture
    assert "## Index Storage" in architecture
    assert "## Query Execution" in architecture

    assert "date:this-week" in dsl
    assert "size:>10M" in dsl
    assert "-path:node_modules" in dsl

    assert "SPEC §6.3" in performance
    assert "tests/perf/test_cold_start.py" in performance
