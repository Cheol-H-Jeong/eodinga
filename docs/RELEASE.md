# Release

This guide documents how the repository-local release inputs are validated before the orchestrator publishes artifacts.

## Release Inputs

The release surface for `0.1.x` consists of:

- version strings in `pyproject.toml` and `eodinga/__init__.py`
- the top entry in `CHANGELOG.md`
- README and docs pages that describe the current contract
- Windows, AppImage, and Debian packaging inputs
- local tags of the form `git tag v0.1.N`

## Required Validation

Run these commands from a Python 3.11 virtualenv with the full dependency surface installed:

```bash
source .venv/bin/activate
pytest -q tests
ruff check eodinga tests
pyright
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml .github/workflows/release-linux.yml
```

If the round changed Qt surfaces, also refresh screenshots before tagging:

```bash
source .venv/bin/activate
python scripts/render_docs_screenshots.py
```

## Cut Sequence

1. Confirm the next patch number is unused in `git tag -l 'v0.1.*'`.
2. Bump `pyproject.toml` and `eodinga/__init__.py`.
3. Add the new `CHANGELOG.md` entry at the top of the file.
4. Re-run `pytest -q tests/unit` after each logical commit and the full validation set before the final tag.
5. Create the local tag with `git tag v0.1.N`.

## Packaging Outputs

- `python packaging/build.py --target windows-dry-run` validates the PyInstaller and Inno Setup inputs without producing a signed installer.
- `python packaging/build.py --target linux-appimage-dry-run` validates the AppImage recipe and staging assets.
- `python packaging/build.py --target linux-deb-dry-run` validates the Debian staging tree and manifest.

The orchestrator is responsible for the final rebase, push, and any GitHub release publication. This document only covers the repository-local contract that must be green first.
