# Release Workflow

This document expands the short checklist in [ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) into a repository-local release flow for `0.1.x`.

## Pick The Version

1. Inspect existing tags with `git tag -l | sort -V | tail -3`.
2. Choose the next unused patch version as `0.1.N`.
3. Bump both `pyproject.toml` and `eodinga/__init__.py` to that version.
4. Keep that version bump isolated to the release metadata commit for the round.
5. Confirm the candidate tag does not already exist locally before creating it.
6. In worker worktrees, fetch and reset to `origin/main` before starting the round so the chosen patch number is based on the latest landed tags.

## Version Collision Guard

Use one explicit refresh before you cut the metadata commit:

```bash
git fetch origin main --tags && git tag -l | sort -V | tail -5
```

- Pick `0.1.N` only after that tag refresh, not from a stale local clone.
- If another worker lands the same patch version before you tag, choose the next unused patch number and update the metadata commit instead of moving an existing tag.
- Keep the version bump and changelog update in the last commit of the round so retargeting from `0.1.N` to `0.1.N+1` stays small and auditable.

## Metadata Retarget Flow

When another worker lands your candidate patch version first, keep the earlier docs or feature commits untouched and retarget only the final metadata change:

1. `git fetch origin main --tags`
2. choose the next unused `0.1.N`
3. update `pyproject.toml`, `eodinga/__init__.py`, and the top `CHANGELOG.md` entry only
4. rerun `pytest -q tests/unit`
5. create the new local tag and leave the earlier feature/docs commits as-is

This preserves reviewability: the only rewritten evidence is the release metadata that depended on the tag number.

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

If the one-command pass fails, fix the first failing stage before rerunning. Later packaging or workflow failures are not actionable until the earlier repo-health checks are clean.

Recommended order:

1. `pytest -q tests/unit` after every logical commit.
2. `pytest -q tests` once the candidate release branch is assembled.
3. `ruff`, `pyright`, GUI smoke, packaging dry-runs, and workflow lint after the full test pass.

Optional perf evidence belongs after the default gate, not inside it. If you run `EODINGA_RUN_PERF=1 pytest -q tests/perf -s`, capture the printed benchmark summaries and keep failing perf output out of the release baseline or changelog until the regression is understood.

## Artifact Inventory

Before tagging, know which release inputs this repository expects to exist:

- `README.md`, `docs/ACCEPTANCE.md`, `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `docs/PERFORMANCE.md`, and `docs/RELEASE.md` as the shipped operator docs set.
- `docs/man/eodinga.1` as the generated CLI reference derived from the current argparse surface.
- `docs/screenshots/*.png` as offscreen-rendered evidence of the current Qt surfaces.
- `packaging/dist/` dry-run manifests for Windows, AppImage, and Debian audits.
- `.github/workflows/release-windows.yml` and `.github/workflows/release-linux.yml` as linted release automation inputs.

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

## Failure Priority

When the release pass fails, repair the first broken proof in this order:

1. docs contract or generated asset drift
2. unit or full-test failures
3. GUI smoke mismatches
4. packaging dry-run failures
5. workflow-lint failures

This keeps the debugging path narrow. A packaging failure is not actionable until the docs contract and repository-health checks are already green.

## Packaging Audit Checklist

Use this review table after each matching dry run:

| Surface | Command | What to confirm before tagging |
| --- | --- | --- |
| Windows installer | `python packaging/build.py --target windows-dry-run` | PyInstaller bundle metadata, Inno Setup rendering, shipped docs payload |
| Linux AppImage | `python packaging/build.py --target linux-appimage-dry-run` | rendered recipe version, artifact naming, bundled docs list |
| Linux `.deb` | `python packaging/build.py --target linux-deb-dry-run` | staged desktop entry, icon, compressed changelog, docs payload |

Treat `packaging/dist/` as the review surface. A green dry run without a reviewed manifest is not a completed release check.

## Artifact Inspection Commands

Use one direct inspection command per artifact family instead of opening the whole tree and guessing:

```bash
find packaging/dist -maxdepth 2 -type f | sort
```

```bash
sed -n '1,200p' packaging/dist/windows-dry-run-audit.json
```

```bash
sed -n '1,200p' packaging/dist/linux-appimage-audit.json
```

```bash
sed -n '1,200p' packaging/dist/linux-deb-audit.json
```

If the exact filename changes, list the directory first and inspect the current manifest rather than relying on stale shell history.

## Artifact Review Worksheet

Use these prompts against the actual files under `packaging/dist/` before cutting the local tag:

| Artifact family | Review question |
| --- | --- |
| generated man page | does `docs/man/eodinga.1` still describe the current subcommands and flags from argparse? |
| screenshots | do the rendered PNGs still show the visible text, keyboard hints, and surfaces described in `README.md`? |
| Windows dry run | does the staged payload list the docs and launcher/runtime files the release docs claim exist? |
| Linux AppImage / `.deb` dry runs | do artifact names, packaged docs, and compressed changelog outputs match the release notes and README wording? |

## Release Audit Selection

Pick the audit command by the scope of the question:

| Question | Command | Inspect first |
| --- | --- | --- |
| "Did one platform target stage the right payload?" | `python packaging/build.py --target windows-dry-run` or the matching Linux target | the matching platform-specific `packaging/dist/*-audit.json` file |
| "Did the release-wide pass point at all expected audits?" | `python packaging/build.py --target release-dry-run` | `packaging/dist/release-dry-run-audit.json` |
| "Did a docs-only round refresh the right derived evidence?" | `pytest -q tests/unit/test_docs_assets.py` plus the matching GUI smoke or platform dry run | the derived asset path or platform audit referenced by the changed docs |

Prefer the platform-specific audit when one target failed. The release-wide audit is the coordinator summary, not a replacement for reading the failing manifest itself.

## Release Notes Template

Keep the changelog wording short and evidence-backed:

1. Start each bullet with the user-visible or operator-visible effect.
2. Name the subsystem only when it helps the reviewer map the change to evidence.
3. If the round is docs-only, say which guide changed and what workflow it clarifies.
4. Avoid speculative language such as "prepares for" or "enables future".

Example shape:

```text
- Clarified the docs-only release pass so contributors rerun the matching dry run and inspect `packaging/dist/` before tagging.
- Added a contributor handoff packet checklist, reducing ambiguity about which commands and generated assets were actually reviewed.
```

## Tag Decision Path

```text
round changes assembled
    |
    +--> pytest / ruff / pyright / GUI smoke green?
    |       |
    |       +--> no: fix repo state first
    |
    +--> packaging dry-runs and workflow lint green?
    |       |
    |       +--> no: inspect packaging/dist/ and repair staged inputs
    |
    +--> shipped docs + derived assets match current runtime?
    |       |
    |       +--> no: refresh docs or regenerate assets
    |
    +--> cut metadata commit + local tag
```

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
5. If you also ran the opt-in perf suite, only refresh `docs/PERFORMANCE.md` when the benchmark completed cleanly and the new table comes from that same commit.

## Docs-Only Validation Pass

When the round changes shipped docs but not runtime code, use one explicit pass that still exercises the docs-dependent release inputs:

```bash
source .venv/bin/activate && pytest -q tests/unit/test_docs_assets.py && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)" && python packaging/build.py --target windows-dry-run && python packaging/build.py --target linux-appimage-dry-run && python packaging/build.py --target linux-deb-dry-run
```

If CLI help or visible GUI surfaces changed, regenerate the man page or screenshots before running that pass. Do not tag a docs-only round from stale derived assets.

## Evidence Review Questions

Before you cut the local tag, answer these against the actual outputs:

1. Does `tests/unit/test_docs_assets.py` prove the new sections and links are part of the shipped docs contract?
2. Does the offscreen GUI smoke path still match any screenshots or keyboard flows described in the docs?
3. Do the dry-run manifests under `packaging/dist/` agree with the packaged artifacts the docs claim exist?
4. If the round changed release instructions, can a reviewer follow the documented commands without inventing missing steps?

## Cut The Local Release

1. Commit the release metadata changes.
2. Create the local tag with `git tag v0.1.N`.
3. Stop after the local tag; the orchestrator owns any later rebase, push, and publication steps.

Single-shot metadata cut:

```bash
git add CHANGELOG.md pyproject.toml eodinga/__init__.py && git commit -m "chore(release): bump to v0.1.N" && git tag v0.1.N
```

Example:

```bash
git add CHANGELOG.md pyproject.toml eodinga/__init__.py
git commit -m "chore(release): bump to v0.1.N"
git tag v0.1.N
```

If `git tag -l "v0.1.N"` already returns a result, stop and pick the next unused patch version instead of moving the existing tag.

Collision check example:

```bash
git fetch origin main --tags && git tag -l "v0.1.*" | sort -V | tail -5
```

## Collision And Retag Rules

- Never move or delete an existing local release tag just to reuse the version number.
- If another worker landed the same candidate version first, fetch tags again, pick the next unused patch number, and update the release metadata commit instead of force-retagging.
- If the final gate fails after the metadata commit, fix the issue in a new commit and recreate the local tag on the new tip only after the gate is green again.

## Tag Provenance

- The local release tag should always point at the metadata commit for the round, not the last feature/docs commit before versioning.
- If you must retarget because of a version collision, recreate the local tag only after the updated metadata commit is green.
- The orchestrator may rebase and publish later, but the worker handoff should already prove which exact commit the local tag was cut from.

## Retargeting Metadata After A Collision

When a parallel worker lands your planned patch number first:

1. `git fetch origin main --tags`
2. choose the next unused `0.1.N`
3. update only the metadata files: `pyproject.toml`, `eodinga/__init__.py`, and the top `CHANGELOG.md` entry
4. rerun `pytest -q tests/unit`
5. recreate the local `v0.1.N` tag on the new metadata commit

Keep the earlier docs or feature commits unchanged so the round stays reviewable and easy to rebase.

## Docs Asset Drift Fix Path

If only the docs evidence is stale while runtime tests are green:

1. regenerate the affected asset with `python scripts/generate_manpage.py` or `python scripts/render_docs_screenshots.py`
2. rerun `pytest -q tests/unit/test_docs_assets.py`
3. rerun only the matching GUI smoke or packaging dry run
4. keep the metadata/tag cut as the last step

Do not rewrite unrelated docs or code just to refresh one generated asset family.

## Handoff Checklist

- Working tree clean except for intended release artifacts.
- `pytest -q tests/unit` green at minimum for each intermediate commit.
- Full repository gate green before final handoff.
- `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py` all agree on `0.1.N`.
- The local tag points at the final commit for the round, not an earlier docs or feature commit.
- The final release commit remains reviewable on its own and does not hide unrelated feature edits.
- `packaging/dist/` has been reviewed for the dry-run targets touched by the round.

## Worker Report Template

Keep the final worker handoff factual and short:

1. the exact command bundle that was run
2. the artifact or manifest paths inspected
3. the changed docs or release-contract sections
4. any skipped validation step with the reason

That is enough for the orchestrator or reviewer to replay the proof without reconstructing the round from git history alone.
