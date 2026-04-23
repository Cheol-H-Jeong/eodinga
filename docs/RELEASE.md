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

## Verify Shipped Docs

Before tagging, confirm:

- `README.md` still matches the current install, CLI, launcher, and DSL behavior.
- `docs/ARCHITECTURE.md` still matches the index lifecycle and packaging surfaces.
- `docs/PERFORMANCE.md` numbers come from a rerun at the documented HEAD.
- Screenshot assets under `docs/screenshots/` still match the current UI, or have been refreshed with `python scripts/render_docs_screenshots.py`.
- `docs/eodinga.1` has been regenerated with `python scripts/generate_man_page.py` if the CLI parser surface changed.

## Build Artifact Audit

Run the dry-run targets before cutting the local tag so the release notes describe shippable artifacts instead of speculative ones:

```bash
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
```

Expected outputs from those audits:

- Windows: rendered PyInstaller inputs plus a validated `eodinga-<version>-win-x64-setup.exe` naming surface.
- Linux AppImage: a populated AppDir recipe and launch metadata audit for the standalone binary bundle.
- Linux Debian: staged package tree, desktop assets, compressed changelog, and control metadata suitable for `.deb` assembly.

## Cut The Local Release

1. Commit the release metadata changes.
2. Create the local tag with `git tag v0.1.N`.
3. Stop after the local tag; the orchestrator owns any later rebase, push, and publication steps.

## Recommended Commit Shape

1. Commit functional or documentation changes in reviewable slices.
2. Reserve the final release commit for `CHANGELOG.md`, `pyproject.toml`, `eodinga/__init__.py`, and any generated release artifacts refreshed for the cut.
3. Tag only after that final commit and a clean rerun of the gate.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
