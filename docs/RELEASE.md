# Release Workflow

This guide describes how to cut a repository-local `0.1.N` release candidate for `eodinga`. It assumes the orchestrator handles any later push, rebase, or GitHub release publication.

## Preconditions

- Work from a tree synced to the current `main` tip.
- Use Python 3.11 with `.venv` activated.
- Confirm the next patch number by checking recent tags:
  `git tag -l | sort -V | tail -3`

## Quality Gate

Run the full local acceptance gate before changing the version:

```bash
pytest -q tests
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml
```

## Release Edits

1. Bump `pyproject.toml` and `eodinga/__init__.py` to the same next `0.1.N` version.
2. Add a new top entry to `CHANGELOG.md` with the measurable changes in the round.
3. Refresh `README.md` or the supporting docs if user-visible behavior, packaging, or screenshots changed.

## Local Tag

Create the repository-local tag after the release edits and validation succeed:

```bash
git tag v0.1.N
```

Verify the tag exists locally:

```bash
git tag -l | sort -V | tail -5
```

## Handoff

- Leave the branch rebased and committed locally.
- Do not push from the worker.
- Hand off the branch, changelog entry, and local tag to the orchestrator for the final integration step.
