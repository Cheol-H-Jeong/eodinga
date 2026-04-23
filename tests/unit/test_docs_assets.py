from __future__ import annotations

from pathlib import Path

from eodinga.gui.docs import render_doc_screenshots


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_render_doc_screenshots_writes_expected_assets(tmp_path: Path, qapp) -> None:
    screenshots = render_doc_screenshots(tmp_path)

    assert set(screenshots) == {"app-window", "launcher-window", "index-progress", "settings-window"}
    assert screenshots["app-window"].name == "app-window.png"
    assert screenshots["launcher-window"].name == "launcher-window.png"
    assert screenshots["index-progress"].name == "index-progress.png"
    assert screenshots["settings-window"].name == "settings-window.png"
    for asset in screenshots.values():
        assert asset.exists()
        assert asset.stat().st_size > 0


def test_docs_reference_expected_assets_and_guides() -> None:
    root = _repo_root()
    readme = (root / "README.md").read_text(encoding="utf-8")
    acceptance = (root / "docs" / "ACCEPTANCE.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    contributing = (root / "docs" / "CONTRIBUTING.md").read_text(encoding="utf-8")
    dsl = (root / "docs" / "DSL.md").read_text(encoding="utf-8")
    performance = (root / "docs" / "PERFORMANCE.md").read_text(encoding="utf-8")
    release = (root / "docs" / "RELEASE.md").read_text(encoding="utf-8")

    assert "![Main application window]" in readme
    assert "![Launcher window]" in readme
    assert "![Index progress window]" in readme
    assert "![Settings window]" in readme
    assert "## Install" in readme
    assert "## Quick Start" in readme
    assert "## Feature Overview" in readme
    assert "## Acceptance Quickcheck" in readme
    assert "## DSL Cheatsheet" in readme
    assert "## Supported Content Types" in readme
    assert "## Hotkey" in readme
    assert "## Config and Data Paths" in readme
    assert "## Recovery and Troubleshooting" in readme
    assert "## Limitations" in readme
    assert "## Packaging" in readme
    assert "## Contributing" in readme
    assert "## Release Process" in readme
    assert "linux-deb-dry-run" in readme
    assert "docs/DSL.md" in readme
    assert "docs/ACCEPTANCE.md" in readme
    assert "docs/ARCHITECTURE.md" in readme
    assert "docs/CONTRIBUTING.md" in readme
    assert "docs/PERFORMANCE.md" in readme
    assert "docs/RELEASE.md" in readme
    assert "pytest -q tests && ruff check eodinga tests" in readme
    assert "python packaging/build.py --target windows-dry-run" in readme
    assert "yamllint .github/workflows/release-windows.yml" in readme
    assert "rendered offscreen from the real Qt surfaces" in readme

    assert "## Required Commands" in acceptance
    assert "pip install -e .[all]" in acceptance
    assert "eodinga --help" in acceptance
    assert "index" in acceptance
    assert "watch" in acceptance
    assert "search" in acceptance
    assert "stats" in acceptance
    assert "gui" in acceptance
    assert "doctor" in acceptance
    assert "version" in acceptance
    assert "QT_QPA_PLATFORM=offscreen" in acceptance
    assert "windows-dry-run" in acceptance
    assert "yamllint .github/workflows/release-windows.yml" in acceptance
    assert "README is part of the acceptance surface" in acceptance
    assert "git tag v0.1.N" in acceptance

    assert "## Runtime Flow" in architecture
    assert "## Data Flow Diagram" in architecture
    assert "## Module Map" in architecture
    assert "## Index Storage" in architecture
    assert "## Index Lifecycle Sequence" in architecture
    assert "## Startup Recovery" in architecture
    assert "## Rebuild Sequence" in architecture
    assert "## Query Execution" in architecture
    assert "## Live Update Sequence" in architecture
    assert "## Packaging Surfaces" in architecture
    assert "compressed changelog" in architecture

    assert "## Local Setup" in contributing
    assert "## Daily Workflow" in contributing
    assert "## Quality Gates" in contributing
    assert "## Scope Guardrails" in contributing
    assert "## Documentation Expectations" in contributing
    assert "scripts/render_docs_screenshots.py" in contributing
    assert "## Test Selection Guide" in contributing
    assert "## Commit and Release Notes" in contributing

    assert "modified:today" in dsl
    assert "created:2026-04-23" in dsl
    assert "date:this-week" in dsl
    assert "date:yesterday" in dsl
    assert "size:>10M" in dsl
    assert "is:duplicate" in dsl
    assert "regex:true" in dsl
    assert "-path:node_modules" in dsl
    assert "## Operator Notes" in dsl

    assert "SPEC §6.3" in performance
    assert "tests/perf/test_cold_start.py" in performance
    assert "test_rebuild_cold_start_throughput" in performance
    assert "EODINGA_PERF_REBUILD_MIN_FPS" in performance
    assert "## Running the Suite" in performance
    assert "## Baseline" in performance
    assert "## Profiling Workflow" in performance

    assert "## Pick The Version" in release
    assert "## Refresh Release Notes" in release
    assert "## Run The Gate" in release
    assert "## Verify Shipped Docs" in release
    assert "## Cut The Local Release" in release
    assert "## Handoff Checklist" in release
    assert "git tag v0.1.N" in release
