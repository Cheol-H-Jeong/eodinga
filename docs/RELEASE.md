# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.

## Refresh Release Notes

1. Add a new top entry in `CHANGELOG.md`.
2. Summarize only the measurable user-facing or operator-facing changes that landed in the round.
3. Keep the changelog entry aligned with the final commit set instead of speculative future work.

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

## Build Matrix

The release process currently ships three packaging targets:

| Target | Command | Expected artifact shape |
| --- | --- | --- |
| Windows installer dry run | `python packaging/build.py --target windows-dry-run` | Rendered Inno script plus an audit payload proving version sync, installer metadata, and source-derived hidden imports |
| Linux AppImage dry run | `python packaging/build.py --target linux-appimage-dry-run` | AppDir-style audit payload proving launcher shim, desktop file, icon, and versioned output naming |
| Linux Debian dry run | `python packaging/build.py --target linux-deb-dry-run` | Debian package-root audit proving control metadata, launcher shim, desktop entry, SVG icon, license, and compressed changelog |

If any dry-run audit fails, fix the input contract before tagging. The dry runs are the intended non-destructive way to verify packaging metadata on a development machine.

## Verify Shipped Docs

Before tagging, confirm:

- `README.md` still matches the current install, CLI, launcher, and DSL behavior.
- `docs/ARCHITECTURE.md` still matches the index lifecycle and packaging surfaces.
- `docs/PERFORMANCE.md` numbers come from a rerun at the documented HEAD.
- Screenshot assets under `docs/screenshots/` still match the current UI, or have been refreshed with `python scripts/render_docs_screenshots.py`.

## Refresh Generated Surfaces

Before the final release commit, refresh the docs that mirror live command or UI surfaces:

1. Re-run `python -m eodinga --help` and each subcommand help page if you changed the CLI, then update [eodinga.1.md](/tmp/eodinga-parallel/worker-4/docs/eodinga.1.md).
2. Re-run `python scripts/render_docs_screenshots.py` if GUI layout, launcher behavior, or settings copy changed.
3. Update `README.md` and `docs/ARCHITECTURE.md` in the same round if a change altered the public contract or operating model.

## Cut The Local Release

1. Commit the release metadata changes.
2. Create the local tag with `git tag v0.1.N`.
3. Stop after the local tag; the orchestrator owns any later rebase, push, and publication steps.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- `docs/eodinga.1.md` and `docs/screenshots/` match the shipped CLI and GUI surfaces for that tag.
