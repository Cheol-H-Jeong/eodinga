# Contributing

This repository favors small, verifiable improvements. Keep each change scoped, reproducible, and aligned with the current `0.1.x` lexical-search contract.

## Local Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[all]
```

## Daily Workflow

1. Sync your branch or worktree from the latest `main`.
2. Run the smallest relevant test slice first.
3. Keep each commit independently green with `pytest -q tests/unit`.
4. Run the full local gate before handing off a release candidate.
5. Update docs and screenshots when the visible or operator-facing contract changes.

## Suggested Command Order

Use one clean pass instead of ad-hoc retries:

```bash
git fetch origin main && git reset --hard origin/main
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev,parsers,gui]
pytest -q tests/unit
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
```

After the focused slice is green, run the broader acceptance gate before release handoff.

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
- Regenerate `docs/man/eodinga.1` with `python scripts/generate_manpage.py` after CLI parser changes.
- Keep `CHANGELOG.md` aligned with landed behavior only; avoid speculative release notes.

## Derived Asset Matrix

| If you changed... | Refresh or rerun... |
| --- | --- |
| CLI parser, flags, or subcommands | `python scripts/generate_manpage.py` and `pytest -q tests/unit/test_docs_assets.py` |
| Visible GUI text or layout used in docs | `python scripts/render_docs_screenshots.py` and `pytest -q tests/unit/test_docs_assets.py` |
| README or guide wording only | `pytest -q tests/unit/test_docs_assets.py` |
| Packaging or release docs | the matching `packaging/build.py --target ...-dry-run` command plus `pytest -q tests/unit/test_docs_assets.py` |

## Docs Refresh Order

When a change affects the shipped contract, refresh docs in this order:

1. Update the primary contract in `README.md`.
2. Update the deeper reference in the relevant `docs/*.md` guide.
3. Regenerate derived assets such as screenshots or `docs/man/eodinga.1`.
4. Re-run `pytest -q tests/unit/test_docs_assets.py` before the broader gate.
5. Re-run any matching packaging dry run if the docs now describe packaging behavior or artifacts differently.

## Docs-Only Workflow

Use this path when the shipped contract changed but runtime code did not:

1. Update `README.md` first because it is the shortest operator-facing contract.
2. Update the deeper guide under `docs/` that explains the same behavior in more detail.
3. Refresh derived assets only if the round touched CLI parser output or visible GUI surfaces.
4. Re-run `pytest -q tests/unit/test_docs_assets.py` before broader unit coverage.
5. Add the changelog entry and release metadata bump for the round; docs-only changes still ship.

## Test Selection Guide

- Query/compiler changes: `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py`
- GUI/launcher changes: `pytest -q tests/unit/test_gui_app.py tests/unit/test_gui_launcher.py tests/unit/test_docs_assets.py`
- Index/storage/watcher changes: `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py`
- Packaging changes: `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py`

## Review Checklist

- Confirm the change stayed inside one theme and one logical commit at a time.
- Confirm `README.md` and the deeper `docs/*.md` guide do not contradict each other.
- Confirm every dry-run command shown in docs still exists exactly as written.
- Confirm screenshots and `docs/man/eodinga.1` were refreshed if the round touched those derived surfaces.
- Confirm the changelog entry describes landed behavior instead of future intent.

## Commit and Release Notes

- Use Conventional Commits.
- Keep `CHANGELOG.md` append-only with the newest round at the top.
- Patch releases use `0.1.N`; bump `pyproject.toml` and `eodinga/__init__.py` together.
- Local tags are created during the release-cut handoff flow documented in [RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md).
- Docs-only rounds still require a changelog entry and local tag when the shipped contract changed.
- If a change cannot stay inside one theme or one logical commit, stop and split it before proceeding.

## Handoff Expectations

- Leave the working tree clean except for intentional round output.
- Mention the exact test slice you ran if it was narrower than the full gate.
- If a docs statement depends on a local measurement, capture the command that produced it in the same round.
- If you could not regenerate a derived asset, do not paper over that gap with prose; leave the existing asset untouched and call out the blocker.
