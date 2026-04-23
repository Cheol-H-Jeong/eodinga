# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.
4. Keep that version bump isolated to the release metadata commit for the round.
5. Confirm the local tag you plan to create does not already exist on `main`.

## Refresh Release Notes

1. Add a new top entry in `CHANGELOG.md`.
2. Summarize only the measurable user-facing or operator-facing changes that landed in the round.
3. Keep the changelog entry aligned with the final commit set instead of speculative future work.
4. Mention docs-only rounds explicitly when the shipped contract changed but runtime code did not.

Recommended changelog shape:

- one bullet per logical commit or user-visible outcome
- concrete nouns over umbrella phrases like "improved docs"
- version/date heading first, newest entry at the top

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

One-command local release pass:

```bash
source .venv/bin/activate && pytest -q tests && ruff check eodinga tests && pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)" && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)" && python packaging/build.py --target windows-dry-run && python packaging/build.py --target linux-appimage-dry-run && python packaging/build.py --target linux-deb-dry-run && yamllint .github/workflows/release-windows.yml && yamllint .github/workflows/release-linux.yml
```

Recommended order:

1. `pytest -q tests/unit` after every logical commit.
2. `pytest -q tests` once the candidate release branch is assembled.
3. `ruff`, `pyright`, GUI smoke, packaging dry-runs, and workflow lint after the full test pass.

## Verify Shipped Docs

Before tagging, confirm:

- `README.md` still matches the current install, CLI, launcher, and DSL behavior.
- `docs/ARCHITECTURE.md` still matches the index lifecycle and packaging surfaces.
- `docs/PERFORMANCE.md` numbers come from a rerun at the documented HEAD.
- `docs/man/eodinga.1` has been regenerated if `eodinga.__main__` changed.
- Screenshot assets under `docs/screenshots/` still match the current UI, or have been refreshed with `python scripts/render_docs_screenshots.py`.
- Docs-only rounds still ran the relevant docs asset tests and did not drift from the current CLI or packaging surface.

Documentation refresh commands:

```bash
python scripts/generate_manpage.py
python scripts/render_docs_screenshots.py
pytest -q tests/unit/test_docs_assets.py
```

## Docs-Only Release Rounds

If the round changed shipped documentation but not runtime code:

1. Keep the docs commits separate from the final release metadata commit.
2. Make the changelog entry say explicitly that the behavioral surface is unchanged.
3. Still bump the patch version, because the shipped release bundle changed.
4. Re-run the standard gate so packaging, CLI docs, and screenshots remain auditable at the tagged commit.

## Cut The Local Release

1. Commit the release metadata changes.
2. Create the local tag with `git tag v0.1.N`.
3. Stop after the local tag; the orchestrator owns any later rebase, push, and publication steps.

Example:

```bash
git add CHANGELOG.md pyproject.toml eodinga/__init__.py
git commit -m "chore(release): bump to v0.1.N"
git tag v0.1.N
```

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- The local tag points at the final commit for the round, not an earlier docs or feature commit.
- If the round was docs-only, the handoff note says that explicitly and names the updated guides.
