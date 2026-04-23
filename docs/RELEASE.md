# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.

Do not pick a version that exists only in your worktree. The source of truth is the tag set reachable from `main`.

## Refresh Release Notes

1. Add a new top entry in `CHANGELOG.md`.
2. Summarize only the measurable user-facing or operator-facing changes that landed in the round.
3. Keep the changelog entry aligned with the final commit set instead of speculative future work.

## Confirm Artifact Inputs

Before you spend time on the full release gate, confirm the files that packaging consumes still agree:

| Surface | What to verify |
| --- | --- |
| `pyproject.toml` | Package version matches the intended `0.1.N` |
| `eodinga/__init__.py` | Runtime version matches `pyproject.toml` |
| `CHANGELOG.md` | Newest entry is the version being cut |
| `README.md` | Install, CLI, launcher, DSL, packaging, and recovery copy still matches the shipped product |
| `docs/screenshots/` | Visible assets still match current Qt surfaces |
| `packaging/windows/eodinga.iss` and `packaging/pyinstaller.spec` | No stale installer metadata or missing runtime imports for the release surface |

## Run The Gate

Use the same commands as the acceptance guide:

```bash
pytest -q tests
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml
yamllint .github/workflows/release-linux.yml
```

## Minimum Intermediate Gate

Each logical commit in the round should leave `pytest -q tests/unit` green even before you reach the final release commit. This keeps later rebases and cherry-picks tractable when multiple workers land in parallel.

## Verify Shipped Docs

Before tagging, confirm:

- `README.md` still matches the current install, CLI, launcher, and DSL behavior.
- `docs/ARCHITECTURE.md` still matches the index lifecycle and packaging surfaces.
- `docs/PERFORMANCE.md` numbers come from a rerun at the documented HEAD.
- Screenshot assets under `docs/screenshots/` still match the current UI, or have been refreshed with `python scripts/render_docs_screenshots.py`.

If a round changed no screenshots or perf numbers, say that explicitly in the handoff instead of leaving reviewers to infer it.

## Artifact Dry-Run Expectations

Use the dry-run outputs as contract checks, not as optional smoke tests:

| Command | Expected signal |
| --- | --- |
| `python packaging/build.py --target windows-dry-run` | Renders the Windows installer inputs, PyInstaller payload, and installer metadata without missing imports or version drift |
| `python packaging/build.py --target linux-appimage-dry-run` | Verifies AppImage recipe inputs and launch surface without building the final artifact |
| `python packaging/build.py --target linux-deb-dry-run` | Verifies Debian package staging, shipped docs, desktop entry, and metadata |
| `yamllint .github/workflows/release-windows.yml` | Windows release workflow remains syntactically valid |
| `yamllint .github/workflows/release-linux.yml` | Linux release workflow remains syntactically valid |

## Cut The Local Release

1. Commit the release metadata changes.
2. Create the local tag with `git tag v0.1.N`.
3. Stop after the local tag; the orchestrator owns any later rebase, push, and publication steps.

Tag only after the final gate passes. If you need another fix commit after tagging, delete and recreate the local tag before handoff so the tag still points at the exact release candidate commit.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- Local tag `v0.1.N` points at the same commit as the final release metadata change.
- Any intentionally skipped screenshot refresh or perf rerun is called out explicitly in the handoff.

## Rollback Boundaries

- Do not rewrite or delete tags that already exist on `main`.
- If the full gate fails after the version bump, fix forward in the same worktree; do not leave a mismatched version/changelog pair committed.
- If packaging-only validation fails, prefer reverting the release metadata commit locally and retrying once the packaging issue is fixed, rather than handing off an already-invalid candidate.
