# Acceptance Guide

This guide turns SPEC §9 into a concrete release checklist for the current repository state.

## Required Commands

Install the full local-dev surface on Python 3.11:

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[all]
```

Check the CLI surface:

```bash
eodinga --help
```

The top-level help must list exactly these seven subcommands:

- `index`
- `watch`
- `search`
- `stats`
- `gui`
- `doctor`
- `version`

Run the default quality gate:

```bash
pytest -q tests
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"
```

Run the packaging and workflow checks:

```bash
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml
yamllint .github/workflows/release-linux.yml
```

One-command acceptance pass:

```bash
source .venv/bin/activate && pytest -q tests && ruff check eodinga tests && pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)" && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)" && python packaging/build.py --target windows-dry-run && python packaging/build.py --target linux-appimage-dry-run && python packaging/build.py --target linux-deb-dry-run && yamllint .github/workflows/release-windows.yml && yamllint .github/workflows/release-linux.yml
```

Run it as written. If it fails, investigate the first failing stage before rerunning; the gate is ordered so earlier commands rule out noise in later packaging or workflow steps.

## What The Gate Covers

- `pytest -q tests` exercises the unit, integration, safety, packaging, and GUI-offscreen regressions, including the end-to-end index-and-search path.
- `ruff check eodinga tests` keeps the runtime and tests lint-clean.
- `pyright --outputjson` must report `errorCount: 0`.
- The offscreen GUI smoke command must instantiate the main window and launcher without a display server.
- `windows-dry-run` must render the PyInstaller and Inno Setup inputs and write the audit manifest under `packaging/dist/`.
- `linux-appimage-dry-run` and `linux-deb-dry-run` must render the Linux packaging inputs without mutating user data paths.
- `yamllint` validates the release workflow YAML shipped in `.github/workflows/release-windows.yml`.

## Failure Triage Order

1. Test or lint failure: fix the repo state before touching packaging or release metadata.
2. GUI smoke failure: inspect the offscreen Qt path before assuming the packaging recipe is wrong.
3. Packaging dry-run failure: review the generated manifest or staged payload summary under `packaging/dist/`.
4. Workflow lint failure: fix the shipped workflow YAML before cutting the local tag.

## Derived Docs Checks

Before tagging, re-run the doc-asset checks that pin shipped documentation against the real runtime surface:

```bash
python scripts/generate_manpage.py
python scripts/render_docs_screenshots.py
pytest -q tests/unit/test_docs_assets.py
```

These commands are required when CLI help, visible Qt surfaces, or operator-facing docs change.

Treat the generated man page, screenshots, and dry-run manifests as shipped release inputs. Review them after regeneration instead of assuming the derived assets are correct because the command exited cleanly.

## Documentation Contract

The README is part of the acceptance surface. Before tagging a release, confirm it still documents:

- installation on Linux and Windows
- the default launcher hotkey and keyboard actions
- the DSL entry points and a link to `docs/DSL.md`
- current limitations for lexical-only search, parser coverage, and watcher behavior
- the operator runbook and default config/data/log/crash path locations
- the generated CLI reference at `docs/man/eodinga.1` when the parser surface changes
- the release-gate commands for Windows and Linux packaging dry runs
- the operator runbook in `docs/OPERATIONS.md`

Treat `docs/OPERATIONS.md` as part of the shipped release surface whenever path defaults, env overrides, logging behavior, crash handling, or first-response troubleshooting changes.

## Release Cut

For each improvement round:

1. Bump `pyproject.toml` and `eodinga/__init__.py` to the next `0.1.N` patch version.
2. Add a new top entry to `CHANGELOG.md` summarizing the measurable improvements in that round.
3. Create the local tag with `git tag v0.1.N`.

For docs-only rounds, the changelog entry still needs to say which shipped guide or derived asset changed and why that matters to operators.

The acceptance pass should be green before the version bump and local tag. Keep the metadata cut as the last step so the tag points at a fully validated tree.

Publishing the GitHub Release stays outside this repository-local checklist, but the local tag and changelog entry are required before handing off to the orchestrator.
