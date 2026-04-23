# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.
4. Keep that version bump isolated to the release metadata commit for the round.
5. Confirm the candidate tag does not already exist locally before creating it.

## Refresh Release Notes

1. Add a new top entry in `CHANGELOG.md`.
2. Summarize only the measurable user-facing or operator-facing changes that landed in the round.
3. Keep the changelog entry aligned with the final commit set instead of speculative future work.
4. Mention docs-only rounds explicitly when the shipped contract changed but runtime code did not.
5. If a cross-theme unblocker landed to restore the gate, call it out briefly so the release notes explain why it exists.

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

Documentation refresh commands:

```bash
python scripts/generate_manpage.py
python scripts/render_docs_screenshots.py
pytest -q tests/unit/test_docs_assets.py
```

Treat docs assets as versioned release inputs: do not cut a tag when the checked-in man page or screenshot set no longer matches the current runtime surface.

## Release Evidence Bundle

Capture these release-side facts in the commit set or handoff note before the orchestrator rebases and publishes:

- final `pytest -q tests/unit` result for the last intermediate commit
- full gate result for the final candidate (`pytest -q tests`, `ruff`, `pyright`, GUI smoke, packaging dry-runs, workflow lint)
- the chosen version and the exact tag name
- whether screenshots or `docs/man/eodinga.1` were intentionally unchanged, regenerated, or revalidated only
- any docs-only scope note explaining why runtime code did not change

The goal is not ceremony; it is to make the next person able to see why the tag is safe without reconstructing terminal history.

## Docs-Only Rounds

Use the same release discipline for docs-only changes when the shipped operator contract moved:

1. Update `README.md` and the deeper guide that explains the changed behavior.
2. Regenerate any derived docs assets touched by the round.
3. Re-run `pytest -q tests/unit/test_docs_assets.py` plus the matching packaging dry-run or GUI smoke command.
4. Add a changelog entry that names the docs surface changed and why it matters.

If the docs round cites fresh performance numbers, refresh `docs/PERFORMANCE.md` from a same-day perf run instead of carrying forward the prior baseline table unchanged.

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

If `git tag -l "v0.1.N"` already returns a result, stop and pick the next unused patch version instead of moving the existing tag.

## Local Tag Safety

Before stopping:

1. Confirm `git rev-parse HEAD` is the commit you intend to tag.
2. Run `git tag -l "v0.1.N"` again immediately before `git tag v0.1.N`.
3. Verify `git show --stat --oneline v0.1.N` points at the release metadata commit rather than an earlier docs/content commit.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- The local tag points at the final commit for the round, not an earlier docs or feature commit.
