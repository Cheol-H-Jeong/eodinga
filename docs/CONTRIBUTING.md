# Contributing

This repository favors small, verifiable improvements. Keep each change scoped, reproducible, and aligned with the current `0.1.x` lexical-search contract.

## Local Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[all]
```

## Daily Workflow

1. Sync your branch or worktree from the latest `main`.
2. Run the smallest relevant test slice first.
3. Run the full local gate before handing off a release candidate.
4. Update docs and screenshots when the visible or operator-facing contract changes.
5. Keep release metadata changes (`CHANGELOG.md`, `pyproject.toml`, `eodinga/__init__.py`, local tag) as the last step in the round so intermediate commits stay easy to rework.

## Quality Gates

Default repository gate:

```bash
pytest -q tests
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"
```

Packaging and workflow validation:

```bash
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml
yamllint .github/workflows/release-linux.yml
```

## Scope Guardrails

- Do not edit `SPEC.md`.
- Keep runtime network-free and local-only.
- Treat indexed roots as read-only inputs; runtime writes stay in config and database paths.
- Prefer focused commits over cross-cutting refactors.
- Keep modules under 500 lines unless a preexisting file already exceeds that limit and the change cannot be split further.

## Documentation Expectations

- Update `README.md` when installation, query syntax, keyboard behavior, supported formats, packaging, or recovery behavior changes.
- Refresh `docs/ARCHITECTURE.md` when data flow, rebuild/recovery, or packaging surfaces change materially.
- Refresh `docs/PERFORMANCE.md` only after rerunning the benchmark you are documenting in the same local environment.
- Regenerate the shipped screenshots with `python scripts/render_docs_screenshots.py` after visible GUI changes.

Docs by change type:

- Query semantics or search examples: update `README.md` and `docs/DSL.md`.
- Index lifecycle, watcher behavior, or recovery: update `docs/ARCHITECTURE.md`.
- Packaging or cut flow: update `docs/RELEASE.md`.
- New measurable perf claims: rerun the benchmark first, then update `docs/PERFORMANCE.md`.

## Test Selection Guide

- Query/compiler changes: `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py`
- GUI/launcher changes: `pytest -q tests/unit/test_gui_app.py tests/unit/test_gui_launcher.py tests/unit/test_docs_assets.py`
- Index/storage/watcher changes: `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py`
- Packaging changes: `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py`
- Docs-only changes that touch screenshots or release guidance: `pytest -q tests/unit/test_docs_assets.py tests/unit/test_release_workflows.py tests/unit/test_acceptance_contract.py`

## Screenshot Workflow

1. Start from a green environment with GUI extras installed.
2. Regenerate assets with `python scripts/render_docs_screenshots.py`.
3. Review the resulting files under `docs/screenshots/` instead of editing raster assets manually.
4. Run `pytest -q tests/unit/test_docs_assets.py` so the shipped docs still reference the current asset set.

## Commit and Release Notes

- Use Conventional Commits.
- Keep `CHANGELOG.md` append-only with the newest round at the top.
- Patch releases use `0.1.N`; bump `pyproject.toml` and `eodinga/__init__.py` together.
- Local tags are created during the release-cut handoff flow documented in [RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md).

Release metadata checklist:

- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` must agree on the same `0.1.N`.
- Use the next unused tag from `git tag -l | sort -V | tail -3`.
- Create the local tag only after the full gate is green.
