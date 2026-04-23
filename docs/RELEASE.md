# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.
4. Keep that version bump isolated to the release metadata commit for the round.
5. Confirm the candidate tag does not already exist locally before creating it.
6. In worker worktrees, fetch and reset to `origin/main` before starting the round so the chosen patch number is based on the latest landed tags.

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

For worker rounds, keep the release pass single-shot and non-interactive so a pasted command either finishes cleanly or stops on the first failing stage.

Recommended order:

1. `pytest -q tests/unit` after every logical commit.
2. `pytest -q tests` once the candidate release branch is assembled.
3. `ruff`, `pyright`, GUI smoke, packaging dry-runs, and workflow lint after the full test pass.

## Artifact Inventory

Before tagging, know which release inputs this repository expects to exist:

- `README.md`, `docs/ACCEPTANCE.md`, `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `docs/PERFORMANCE.md`, and `docs/RELEASE.md` as the shipped operator docs set.
- `docs/man/eodinga.1` as the generated CLI reference derived from the current argparse surface.
- `docs/screenshots/*.png` as offscreen-rendered evidence of the current Qt surfaces.
- `packaging/dist/` dry-run manifests for Windows, AppImage, and Debian audits.
- `.github/workflows/release-windows.yml` and `.github/workflows/release-linux.yml` as linted release automation inputs.

## Release Input Matrix

| Release input | Source of truth | Refresh command | Proof command before tag |
| --- | --- | --- | --- |
| `README.md` and shipped guides | checked-in markdown under repo root and `docs/` | edit the docs directly | `pytest -q tests/unit/test_docs_assets.py` |
| `docs/man/eodinga.1` | `eodinga.__main__._build_parser()` via `scripts/generate_manpage.py` | `python scripts/generate_manpage.py` | `pytest -q tests/unit/test_docs_assets.py` |
| `docs/screenshots/*.png` | real Qt widgets rendered through `eodinga.gui.docs` | `python scripts/render_docs_screenshots.py` | `pytest -q tests/unit/test_docs_assets.py` |
| Windows dry-run manifest | `packaging/build.py --target windows-dry-run` plus Inno/PyInstaller inputs | rerun the dry run | `python packaging/build.py --target windows-dry-run` |
| Linux AppImage dry-run manifest | `packaging/build.py --target linux-appimage-dry-run` plus `packaging/linux/appimage-builder.yml` | rerun the dry run | `python packaging/build.py --target linux-appimage-dry-run` |
| Linux Debian dry-run manifest | `packaging/build.py --target linux-deb-dry-run` plus `packaging/linux/deb/` templates | rerun the dry run | `python packaging/build.py --target linux-deb-dry-run` |
| Release automation YAML | `.github/workflows/release-*.yml` | edit the workflow file directly | `yamllint .github/workflows/release-windows.yml && yamllint .github/workflows/release-linux.yml` |
| Version metadata and notes | `pyproject.toml`, `eodinga/__init__.py`, `CHANGELOG.md` | edit together in the final metadata commit | full release gate plus `git tag -l "v0.1.N"` collision check |

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

If only one release input changed, prove that one input directly instead of jumping straight to the whole release pass. The full gate still runs before tagging, but the per-input proof keeps docs-only and packaging-only rounds easier to audit.

## Worker Handoff Rules

1. Keep feature or docs commits separate from the final metadata commit.
2. Make the final commit contain the version bump and changelog update only, unless a last-minute docs asset regeneration is required to match the same round.
3. Create the local tag after that final commit.
4. Do not push tags or release branches from a worker worktree.
5. Hand the orchestrator a clean branch plus the final local tag to rebase and publish.

## Docs-Only Rounds

Use the same release discipline for docs-only changes when the shipped operator contract moved:

1. Update `README.md` and the deeper guide that explains the changed behavior.
2. Regenerate any derived docs assets touched by the round.
3. Re-run `pytest -q tests/unit/test_docs_assets.py` plus the matching packaging dry-run or GUI smoke command.
4. Add a changelog entry that names the docs surface changed and why it matters.

Minimal docs-only proof examples:

- README or guide wording only: `pytest -q tests/unit/test_docs_assets.py`
- Packaging docs changed: `pytest -q tests/unit/test_docs_assets.py && python packaging/build.py --target windows-dry-run`
- GUI docs or screenshots changed: `pytest -q tests/unit/test_docs_assets.py && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"`

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

Collision check example:

```bash
if git tag -l "v0.1.N" | grep -q .; then echo "tag exists"; exit 1; fi
```

## Collision And Retag Rules

- Never move or delete an existing local release tag just to reuse the version number.
- If another worker landed the same candidate version first, fetch tags again, pick the next unused patch number, and update the release metadata commit instead of force-retagging.
- If the final gate fails after the metadata commit, fix the issue in a new commit and recreate the local tag on the new tip only after the gate is green again.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- The local tag points at the final commit for the round, not an earlier docs or feature commit.
- The final release commit remains reviewable on its own and does not hide unrelated feature edits.
