# Contributing

This repository favors small, verifiable improvements. Keep each change scoped, reproducible, and aligned with the current `0.1.x` lexical-search contract.

## Local Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[all]
```

## Daily Workflow

1. Sync your branch or worktree from the latest `main`.
2. Run the smallest relevant test slice first.
3. Keep each commit independently green with `pytest -q tests/unit`.
4. Run the full local gate before handing off a release candidate.
5. Update docs and screenshots when the visible or operator-facing contract changes.

## Module Implementation Workers

When a worker round is driven by an external orchestrator or another agent, treat the requested module spec as a hard scope boundary:

1. Stay inside the listed files and acceptance criteria.
2. Pick the smallest interpretation when a spec is ambiguous and record that decision in the handoff note.
3. Stop and escalate instead of editing files outside the declared scope just to "make it work".
4. Keep the final handoff factual: acceptance criteria status, touched files, and any explicit blocker.

This keeps parallel worker rounds reviewable and avoids hidden cross-theme edits that are hard to rebase later.

## Parallel Worktrees

When multiple workers are landing rounds concurrently, keep the local loop deterministic:

1. Rebase the worktree onto `origin/main` before substantive edits.
2. Stay inside one theme unless a minimal unblocker is required to restore the gate.
3. Keep one logical change per commit and re-run `pytest -q tests/unit` before the next commit.
4. Leave tagging and version bumps for the release-metadata commit at the end of the round.
5. Do not push from a worker worktree; hand off the local commits and tag to the orchestrator.

Required start gate for worker rounds:

```bash
git fetch origin main && git reset --hard origin/main
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev,parsers,gui]
pytest -q tests
ruff check eodinga tests
```

## Suggested Command Order

Use one clean pass instead of ad-hoc retries:

```bash
git fetch origin main && git reset --hard origin/main
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev,parsers,gui]
pytest -q tests/unit
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
```

After the focused slice is green, run the broader acceptance gate before release handoff.

## Quality Gates

Default repository gate:

```bash
pytest -q tests
ruff check eodinga tests
pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)"
QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"
```

Packaging and workflow validation:

```bash
python packaging/build.py --target windows-dry-run
python packaging/build.py --target linux-appimage-dry-run
python packaging/build.py --target linux-deb-dry-run
yamllint .github/workflows/release-windows.yml
yamllint .github/workflows/release-linux.yml
```

Optional perf pass:

```bash
EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

Treat the perf suite as separate diagnostic evidence. If it fails, record the summary lines and the failing threshold instead of overwriting `docs/PERFORMANCE.md` with numbers from a red run.

Commit-level minimum:

```bash
pytest -q tests/unit
```

## Scope Guardrails

- Do not edit `SPEC.md`.
- Keep runtime network-free and local-only.
- Treat indexed roots as read-only inputs; runtime writes stay in config and database paths.
- Prefer focused commits over cross-cutting refactors.
- Keep modules under 500 lines unless a preexisting file already exceeds that limit and the change cannot be split further.

## Documentation Expectations

- Update `README.md` when installation, query syntax, keyboard behavior, supported formats, packaging, or recovery behavior changes.
- Refresh `docs/ARCHITECTURE.md` when data flow, rebuild/recovery, or packaging surfaces change materially.
- Refresh `docs/PERFORMANCE.md` only after rerunning the benchmark you are documenting in the same local environment.
- Regenerate the shipped screenshots with `python scripts/render_docs_screenshots.py` after visible GUI changes.
- Regenerate `docs/man/eodinga.1` with `python scripts/generate_manpage.py` after CLI parser changes.
- Keep `CHANGELOG.md` aligned with landed behavior only; avoid speculative release notes.
- Prefer documenting one-command validation paths when they exist; release and acceptance docs should not require readers to reverse-engineer command order.

## Derived Asset Matrix

| If you changed... | Refresh or rerun... |
| --- | --- |
| CLI parser, flags, or subcommands | `python scripts/generate_manpage.py` and `pytest -q tests/unit/test_docs_assets.py` |
| Visible GUI text or layout used in docs | `python scripts/render_docs_screenshots.py` and `pytest -q tests/unit/test_docs_assets.py` |
| README or guide wording only | `pytest -q tests/unit/test_docs_assets.py` |
| Packaging or release docs | the matching `packaging/build.py --target ...-dry-run` command plus `pytest -q tests/unit/test_docs_assets.py` |

## Theme-Sized Test Guide

Use the smallest green slice that proves the change:

| Theme | First command |
| --- | --- |
| `docs` | `pytest -q tests/unit/test_docs_assets.py` |
| `packaging` | `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py` |
| `query` / `correctness` | `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py` |
| `launcher` / `ux` | `pytest -q tests/unit/test_gui_launcher.py tests/unit/test_gui_app.py tests/unit/test_docs_assets.py` |
| `integration` / `reliability` | `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py` |

## Theme Command Bundles

Use one of these when you want a copy-pasteable, low-noise command bundle for the current theme:

| Theme | Command bundle |
| --- | --- |
| `docs` | `source .venv/bin/activate && pytest -q tests/unit/test_docs_assets.py && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"` |
| `packaging` | `source .venv/bin/activate && pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py && python packaging/build.py --target windows-dry-run` |
| `query` / `correctness` | `source .venv/bin/activate && pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py && ruff check eodinga tests` |
| `launcher` / `ux` | `source .venv/bin/activate && pytest -q tests/unit/test_gui_launcher.py tests/unit/test_gui_app.py tests/unit/test_docs_assets.py && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"` |

- Prefer these explicit bundles over assembling ad-hoc sequences during a worker round.
- If the bundle is green and the round touched a release-facing surface, continue with the broader gate before handoff.

## Docs Refresh Order

When a change affects the shipped contract, refresh docs in this order:

1. Update the primary contract in `README.md`.
2. Update the deeper reference in the relevant `docs/*.md` guide.
3. Regenerate derived assets such as screenshots or `docs/man/eodinga.1`.
4. Re-run `pytest -q tests/unit/test_docs_assets.py` before the broader gate.
5. Re-run any matching packaging dry run if the docs now describe packaging behavior or artifacts differently.

## Docs Round Checklist

Use this when the round is docs-only but still release-bearing:

1. Update the top-level contract in `README.md`.
2. Update the deeper guide under `docs/` that explains the same surface in more detail.
3. Refresh `docs/man/eodinga.1` or screenshots if the documented CLI or UI changed.
4. Re-run `pytest -q tests/unit/test_docs_assets.py`.
5. Re-run the matching packaging dry-run or GUI smoke command when the docs describe those artifacts.
6. Leave the version bump, changelog entry, and local tag for the final metadata commit only.

## Docs Evidence Bundle

Collect the smallest reviewable evidence set that matches the docs you changed:

| If the docs describe... | Required evidence |
| --- | --- |
| CLI surface or examples | `python scripts/generate_manpage.py` plus `pytest -q tests/unit/test_docs_assets.py` |
| Visible GUI or launcher behavior | `python scripts/render_docs_screenshots.py`, `pytest -q tests/unit/test_docs_assets.py`, and `QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)"` |
| Packaged artifacts or release payloads | matching `python packaging/build.py --target ...-dry-run` command plus manifest review under `packaging/dist/` |
| Pure prose or workflow guidance | `pytest -q tests/unit/test_docs_assets.py`, and the nearest matching dry run if the text names shipped artifacts |

Prefer one explicit evidence bundle over ad-hoc retries. The handoff should show why the docs match the runtime, not just that Markdown changed.

## Docs Evidence Escalation

When the first docs proof is green but review risk remains, widen in this order:

1. `pytest -q tests/unit/test_docs_assets.py`
2. regenerate the affected derived asset
3. GUI smoke for screenshot-backed UI text
4. matching packaging dry run for shipped-artifact wording

That order keeps docs rounds cheap by default while still forcing packaging or UI evidence when the prose makes claims about those surfaces.

## Metadata Commit Discipline

- Keep the final metadata commit reviewable: version bump, changelog entry, and local tag cut only.
- If the patch number changes because another worker landed first, retarget just that final metadata commit instead of rewriting earlier docs or feature commits.
- Re-run `pytest -q tests/unit` after retargeting the metadata commit so the branch tip stays demonstrably green.
- Record the exact version-retarget command bundle in the handoff note when a collision happened, so the next reviewer can see that the tag refresh and unit rerun were done after the renumbering.

## Release Retarget Playbook

Use this when another worker lands the same `0.1.N` before your local tag:

1. `git fetch origin main --tags`
2. pick the next unused patch number from `git tag -l | sort -V | tail -5`
3. update only `pyproject.toml`, `eodinga/__init__.py`, and the top `CHANGELOG.md` entry
4. rerun `pytest -q tests/unit`
5. recreate the local tag on the new metadata commit only after the branch tip is green

Do not rewrite earlier docs or feature commits just to retarget the patch number.

## Round Exit Criteria

Before you stop a worker round, confirm:

1. every logical commit left `pytest -q tests/unit` green
2. the last commit before metadata is still theme-scoped and reviewable on its own
3. the metadata/tag cut is isolated to `CHANGELOG.md`, `pyproject.toml`, and `eodinga/__init__.py`
4. the evidence you gathered matches the surface you changed instead of a broader unrelated gate

## Test Selection Guide

- Query/compiler changes: `pytest -q tests/unit/test_dsl_grammar.py tests/unit/test_compiler.py tests/unit/test_executor.py`
- GUI/launcher changes: `pytest -q tests/unit/test_gui_app.py tests/unit/test_gui_launcher.py tests/unit/test_docs_assets.py`
- Index/storage/watcher changes: `pytest -q tests/unit/test_storage.py tests/unit/test_writer.py tests/unit/test_watcher.py`
- Packaging changes: `pytest -q tests/unit/test_build.py tests/unit/test_build_dry_run.py tests/unit/test_inno_script.py tests/unit/test_pyinstaller_spec.py`

## Commit and Release Notes

- Use Conventional Commits.
- Keep `CHANGELOG.md` append-only with the newest round at the top.
- Patch releases use `0.1.N`; bump `pyproject.toml` and `eodinga/__init__.py` together.
- Local tags are created during the release-cut handoff flow documented in [RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md).
- Docs-only rounds still require a changelog entry and local tag when the shipped contract changed.
- If a change cannot stay inside one theme or one logical commit, stop and split it before proceeding.
- The final release commit for a round should carry the version bump, changelog entry, and local tag together so earlier feature or docs commits remain easy to review and rebase.

## Review Checklist

- The documented commands are single-shot and non-interactive where possible.
- Release docs do not describe artifacts or paths that the packaging dry runs do not actually produce.
- README examples use the current query surface and current operator names.
- Derived docs assets are regenerated from code, not edited by hand.
- The final release metadata commit contains only the version/changelog/tag cut unless a same-round asset refresh is required.
- If the docs describe packaged payload contents, the review packet names the exact manifest under `packaging/dist/` that was inspected.

## Docs Review Packet

Before handing off a docs-heavy round, gather one small review packet instead of describing validation from memory:

1. The exact command bundle you ran.
2. The generated asset or manifest path you inspected, such as `docs/man/eodinga.1`, `docs/screenshots/`, or `packaging/dist/`.
3. The specific section headings or examples that changed.
4. Any intentionally skipped validation step, with the reason it was not applicable.

That packet gives the next reviewer a direct path to the same evidence without replaying the entire round.

Suggested packet shape:

```text
Command bundle: <exact command>
Inspected artifact: <path>
Changed sections: <headings or examples>
Skipped step: <n/a or reason>
```

## Packaging Review Checklist

- Run only the dry-run targets that match the packaging surface you changed.
- Inspect `packaging/dist/` instead of trusting command exit status alone.
- Confirm the staged docs payload still matches `README.md`, `docs/ACCEPTANCE.md`, and `docs/man/eodinga.1`.
- If the docs describe a packaged artifact, rerun the corresponding dry run before handoff.

## Command Hygiene

- Prefer single-shot commands that either finish cleanly or stop at the first real failure.
- Avoid interactive prompts in contributor docs unless the workflow genuinely requires them.
- When a command can emit benign noise during setup, suppress it so copy-paste runs stay readable.
- If a docs-only round depends on a packaged artifact, document the exact dry-run command instead of sending the reader to guess between targets.
