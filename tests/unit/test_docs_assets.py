from __future__ import annotations

from pathlib import Path

from eodinga.gui.docs import render_doc_screenshots
from scripts.generate_manpage import render_manpage


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
    operations = (root / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
    contributing = (root / "docs" / "CONTRIBUTING.md").read_text(encoding="utf-8")
    dsl = (root / "docs" / "DSL.md").read_text(encoding="utf-8")
    manpage = (root / "docs" / "man" / "eodinga.1").read_text(encoding="utf-8")
    performance = (root / "docs" / "PERFORMANCE.md").read_text(encoding="utf-8")
    release = (root / "docs" / "RELEASE.md").read_text(encoding="utf-8")

    assert "![Main application window]" in readme
    assert "![Launcher window]" in readme
    assert "![Index progress window]" in readme
    assert "![Settings window]" in readme
    assert "## Install" in readme
    assert "## Install Matrix" in readme
    assert "## Quick Start" in readme
    assert "## Feature Overview" in readme
    assert "## Feature Inventory" in readme
    assert "## Surface Matrix" in readme
    assert "## Acceptance Quickcheck" in readme
    assert "## DSL Cheatsheet" in readme
    assert "## Supported Content Types" in readme
    assert "## Hotkey" in readme
    assert "## Task Recipes" in readme
    assert "## Package Artifacts" in readme
    assert "## Config and Data Paths" in readme
    assert "## Operator Checklist" in readme
    assert "## Recovery and Troubleshooting" in readme
    assert "### Quick Runbook" in readme
    assert "## Limitations" in readme
    assert "## Packaging" in readme
    assert "## Contributing" in readme
    assert "## Release Process" in readme
    assert "linux-deb-dry-run" in readme
    assert "Launcher | global hotkey" in readme
    assert "Packaging audit failed" in readme
    assert "eodinga search 'date:this-week ext:md' --limit 10" in readme
    assert "docs/DSL.md" in readme
    assert "docs/ACCEPTANCE.md" in readme
    assert "docs/ARCHITECTURE.md" in readme
    assert "docs/OPERATIONS.md" in readme
    assert "docs/CONTRIBUTING.md" in readme
    assert "docs/PERFORMANCE.md" in readme
    assert "docs/RELEASE.md" in readme
    assert "docs/man/eodinga.1" in readme
    assert "pytest -q tests && ruff check eodinga tests" in readme
    assert "python packaging/build.py --target windows-dry-run" in readme
    assert "yamllint .github/workflows/release-windows.yml" in readme
    assert "rendered offscreen from the real Qt surfaces" in readme
    assert "CLI-only hacking" in readme
    assert "Windows packaging tooling" in readme
    assert ".[dev,parsers,gui,packaging]" in readme
    assert "Refresh shipped docs assets" in readme
    assert "EODINGA_LOG_PATH" in readme
    assert "~/.local/state/eodinga/logs/eodinga.log" in readme
    assert "%LOCALAPPDATA%\\\\eodinga\\\\crashes\\\\" in readme

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
    assert "linux-appimage-dry-run" in acceptance
    assert "linux-deb-dry-run" in acceptance
    assert "yamllint .github/workflows/release-windows.yml" in acceptance
    assert "yamllint .github/workflows/release-linux.yml" in acceptance
    assert "README is part of the acceptance surface" in acceptance
    assert "git tag v0.1.N" in acceptance
    assert "docs/man/eodinga.1" in acceptance
    assert "## Derived Docs Checks" in acceptance
    assert "python scripts/render_docs_screenshots.py" in acceptance
    assert "One-command acceptance pass" in acceptance

    assert "## Runtime Flow" in architecture
    assert "## Data Flow Diagram" in architecture
    assert "## Module Map" in architecture
    assert "## Index Storage" in architecture
    assert "## SQLite Schema Snapshot" in architecture
    assert "## Index Lifecycle Sequence" in architecture
    assert "## Startup Recovery" in architecture
    assert "## Rebuild Sequence" in architecture
    assert "## Query Execution" in architecture
    assert "## Search Decision Path" in architecture
    assert "## Live Update Sequence" in architecture
    assert "## Documentation Asset Flow" in architecture
    assert "## Release Input Map" in architecture
    assert "## State Ownership" in architecture
    assert "## Failure Domains" in architecture
    assert "## Operator Debug Path" in architecture
    assert "## Packaging Surfaces" in architecture
    assert "## Packaging Review Path" in architecture
    assert "compressed changelog" in architecture
    assert "scripts/generate_manpage.py" in architecture
    assert "scripts/render_docs_screenshots.py" in architecture
    assert "tests/unit/test_docs_assets.py" in architecture
    assert "packaging/dist/" in architecture

    assert "## Quick Commands" in operations
    assert "## Default Paths" in operations
    assert "## Overrides" in operations
    assert "## Symptom Runbook" in operations
    assert "## Recovery Notes" in operations
    assert "## Packaging Review" in operations
    assert "~/.local/state/eodinga/logs/eodinga.log" in operations
    assert "%LOCALAPPDATA%\\\\eodinga\\\\logs\\\\eodinga.log" in operations
    assert "EODINGA_CRASH_DIR" in operations
    assert "EODINGA_DISABLE_FILE_LOGGING=1" in operations
    assert "eodinga stats --json" in operations
    assert "packaging/dist/" in operations

    assert "## Local Setup" in contributing
    assert "## Daily Workflow" in contributing
    assert "## Quality Gates" in contributing
    assert "## Scope Guardrails" in contributing
    assert "## Documentation Expectations" in contributing
    assert "## Derived Asset Matrix" in contributing
    assert "## Parallel Worktrees" in contributing
    assert "Required start gate for worker rounds" in contributing
    assert "## Theme-Sized Test Guide" in contributing
    assert "Commit-level minimum" in contributing
    assert "scripts/generate_manpage.py" in contributing
    assert "scripts/render_docs_screenshots.py" in contributing
    assert "## Docs Refresh Order" in contributing
    assert "## Docs Round Checklist" in contributing
    assert "## Test Selection Guide" in contributing
    assert "## Commit and Release Notes" in contributing
    assert "## Review Checklist" in contributing
    assert "Docs-only rounds still require a changelog entry and local tag" in contributing
    assert "The final release commit for a round should carry the version bump" in contributing

    assert "modified:today" in dsl
    assert "created:2026-04-23" in dsl
    assert "date:this-week" in dsl
    assert "date:yesterday" in dsl
    assert "date:last-week" in dsl
    assert "date:last-month" in dsl
    assert "date:2026-04-01.." in dsl
    assert "created:..2026-04-23" in dsl
    assert "modified:2026-04-23T09:15:30+00:00" in dsl
    assert "size:>10M" in dsl
    assert "is:file" in dsl
    assert "is:dir" in dsl
    assert "is:symlink" in dsl
    assert "is:empty" in dsl
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
    assert "## Repro Checklist" in performance
    assert "## Profiling Workflow" in performance
    assert "## Release Use" in performance
    assert "Each benchmark prints a structured summary line to stdout." in performance
    assert "The defaults currently checked into the suite are:" in performance
    assert "The printed benchmark summary line." in performance

    assert "## Pick The Version" in release
    assert "## Refresh Release Notes" in release
    assert "## Run The Gate" in release
    assert "## Artifact Inventory" in release
    assert "## Verify Shipped Docs" in release
    assert "## Tag Decision Path" in release
    assert "## Worker Handoff Rules" in release
    assert "## Docs-Only Rounds" in release
    assert "## Cut The Local Release" in release
    assert "## Collision And Retag Rules" in release
    assert "## Handoff Checklist" in release
    assert "git tag v0.1.N" in release
    assert "python scripts/generate_manpage.py" in release
    assert "git tag -l \"v0.1.N\"" in release
    assert "Collision check example" in release
    assert "Do not push tags or release branches from a worker worktree." in release
    assert "packaging/dist/" in release

    assert ".TH EODINGA 1" in manpage
    assert ".SH COMMANDS" in manpage
    assert ".SS search" in manpage
    assert ".SH ENVIRONMENT" in manpage
    assert "Set the runtime log verbosity for this invocation." in manpage
    assert "EODINGA_RUN_PERF=1" in manpage
    assert "docs/DSL.md" in manpage
    assert "stats --json" in manpage


def test_generated_manpage_matches_checked_in_asset() -> None:
    root = _repo_root()
    generated = render_manpage()
    checked_in = (root / "docs" / "man" / "eodinga.1").read_text(encoding="utf-8")

    assert checked_in == generated
