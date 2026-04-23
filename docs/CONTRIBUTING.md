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

## Before You Start

- Confirm the change still belongs to the current `0.1.x` lexical-search scope.
- Check `CHANGELOG.md` and recent commits so you do not duplicate an in-flight round.
- Decide up front whether the change affects runtime behavior, shipped docs, packaging, or only tests; that choice determines the minimum gate you should run before asking for review.
- Prefer one logical change per commit. If you cannot explain why two edits ship together, split them.

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

## Change-Type Gate Matrix

| Change type | Run first | Run before handoff |
| --- | --- | --- |
| Query DSL, compiler, executor, ranker | `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py` | Full default repository gate |
| Index writer, storage, migrations, watcher | `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py` | Full default repository gate plus relevant integration tests if behavior spans rebuild and watch |
| GUI or launcher behavior | `pytest -q tests/unit/test_gui_app.py tests/unit/test_gui_launcher.py tests/unit/test_docs_assets.py` | Full default repository gate and refresh screenshots if the visible contract changed |
| Packaging or release scripts | `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py` | Packaging dry-run commands plus the full default repository gate |
| Docs-only changes | `pytest -q tests/unit` | Full default repository gate only if the docs describe release or packaging behavior that you also changed |

## Scope Guardrails

- Do not edit `SPEC.md`.
- Keep runtime network-free and local-only.
- Treat indexed roots as read-only inputs; runtime writes stay in config and database paths.
- Prefer focused commits over cross-cutting refactors.
- Keep modules under 500 lines unless a preexisting file already exceeds that limit and the change cannot be split further.

## Documentation Trigger Map

Update the shipped docs whenever one of these contracts changes:

| If you changed... | Update... |
| --- | --- |
| Install surface, supported extras, CLI verbs, launcher shortcuts, query cheatsheet, screenshots | `README.md` |
| Runtime flow, storage recovery, watcher semantics, packaging surfaces | `docs/ARCHITECTURE.md` |
| Perf numbers or benchmark interpretation | `docs/PERFORMANCE.md` after rerunning the same benchmark at the documented HEAD |
| Release gate, packaging steps, version/tag procedure, handoff expectations | `docs/RELEASE.md` |
| Local workflow, contributor guardrails, doc refresh rules | `docs/CONTRIBUTING.md` |

## Documentation Expectations

- Update `README.md` when installation, query syntax, keyboard behavior, supported formats, packaging, or recovery behavior changes.
- Refresh `docs/ARCHITECTURE.md` when data flow, rebuild/recovery, or packaging surfaces change materially.
- Refresh `docs/PERFORMANCE.md` only after rerunning the benchmark you are documenting in the same local environment.
- Regenerate the shipped screenshots with `python scripts/render_docs_screenshots.py` after visible GUI changes.

## Test Selection Guide

- Query/compiler changes: `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py`
- GUI/launcher changes: `pytest -q tests/unit/test_gui_app.py tests/unit/test_gui_launcher.py tests/unit/test_docs_assets.py`
- Index/storage/watcher changes: `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py`
- Packaging changes: `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py`

## Screenshot Workflow

When a GUI change is visible in the shipped docs:

1. Re-render screenshots with `python scripts/render_docs_screenshots.py`.
2. Inspect the generated images under `docs/screenshots/` rather than assuming the offscreen render matched the live widget state.
3. Update any README copy or keyboard-hint text that the new screenshots would otherwise contradict.
4. Keep screenshot refreshes in the same commit as the UI change when practical, so reviewers can evaluate code and visible output together.

## Commit and Release Notes

- Use Conventional Commits.
- Keep `CHANGELOG.md` append-only with the newest round at the top.
- Patch releases use `0.1.N`; bump `pyproject.toml` and `eodinga/__init__.py` together.
- Local tags are created during the release-cut handoff flow documented in [RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md).

## Review Hygiene

- Mention the exact commands you ran when handing off a round.
- Call out any intentionally skipped gate and why it was not relevant.
- If a docs change records numbers or screenshots, say when and how they were produced.
- Do not claim release readiness unless the version files, changelog, local tag, and acceptance commands all agree.
