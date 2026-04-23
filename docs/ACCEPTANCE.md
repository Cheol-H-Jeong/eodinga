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

## What The Gate Covers

- `pytest -q tests` exercises the unit, integration, safety, packaging, and GUI-offscreen regressions, including the end-to-end index-and-search path.
- `ruff check eodinga tests` keeps the runtime and tests lint-clean.
- `pyright --outputjson` must report `errorCount: 0`.
- The offscreen GUI smoke command must instantiate the main window and launcher without a display server.
- `windows-dry-run` must render the PyInstaller and Inno Setup inputs and write the audit manifest under `packaging/dist/`.
- `linux-appimage-dry-run` and `linux-deb-dry-run` must validate the Linux packaging manifests, launcher shim, and shipped docs.
- `yamllint` validates both release workflow YAML files under `.github/workflows/`.

## Documentation Contract

The README is part of the acceptance surface. Before tagging a release, confirm it still documents:

- installation on Linux and Windows
- the default launcher hotkey and keyboard actions
- the DSL entry points and a link to `docs/DSL.md`
- current limitations for lexical-only search, parser coverage, and watcher behavior
- links to the architecture, performance, contributing, and release docs that make up the shipped contract

Also confirm:

- screenshots under `docs/screenshots/` still match the current Qt surfaces, or have been rerendered with `python scripts/render_docs_screenshots.py`
- `docs/PERFORMANCE.md` numbers came from a rerun at the documented HEAD if that file changed
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` agree on the same `0.1.N` version

## Release Cut

For each improvement round:

1. Bump `pyproject.toml` and `eodinga/__init__.py` to the next `0.1.N` patch version.
2. Add a new top entry to `CHANGELOG.md` summarizing the measurable improvements in that round.
3. Create the local tag with `git tag v0.1.N`.

Recommended local order:

1. `pytest -q tests/unit` after each logical commit.
2. `pytest -q tests` once the round is assembled.
3. `ruff check eodinga tests`, `pyright --outputjson`, GUI smoke, packaging dry-runs, and workflow lint before tagging.

Publishing the GitHub Release stays outside this repository-local checklist, but the local tag and changelog entry are required before handing off to the orchestrator.
