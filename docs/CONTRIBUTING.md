# Contributing

`eodinga` keeps the v0.1 line intentionally narrow: local-first lexical search, deterministic tooling, and small reviewable changes. This guide documents the default workflow for contributors working in this repository.

## Environment

- Use Python 3.11.
- Create a virtualenv and install the full local-dev surface with `pip install -e .[all]`.
- Prefer editable installs while iterating so CLI, GUI, and packaging checks all run against the current checkout.

## Daily Workflow

1. Sync to the current `main` tip before starting a new slice.
2. Run the quality gate after each logical change:
   `pytest -q tests/unit && ruff check eodinga tests && pyright`
3. Re-run `pytest -q tests` before cutting a release-oriented change.
4. If you changed visible Qt surfaces, refresh the shipped screenshots with `python scripts/render_docs_screenshots.py`.

## Scope Rules

- Do not edit `SPEC.md`; it is the contract, not a work area.
- Keep runtime writes inside the config and database paths documented in `README.md`.
- Avoid network behavior in runtime code; the source-level safety checks enforce a local-only product surface.
- Keep modules under 500 lines when practical and prefer focused patches over broad refactors.

## Testing Expectations

- Unit tests should stay green for every commit.
- Run focused integration, packaging, or GUI-offscreen checks when your change touches those surfaces.
- Treat `tests/perf` as opt-in unless you are updating perf-sensitive code or refreshing `docs/PERFORMANCE.md`.

## Commit And Release Hygiene

- Use Conventional Commit subjects.
- Bump `pyproject.toml` and `eodinga/__init__.py` together when cutting the next `0.1.N` round.
- Add the new top entry to `CHANGELOG.md` before tagging.
- Create the local tag `v0.1.N`; the orchestrator handles any later push or publish step.

## Docs And Review

- Update `README.md` when a user-visible command, shortcut, install path, or packaging artifact changes.
- Keep deep technical references in `docs/ARCHITECTURE.md`, `docs/DSL.md`, `docs/PERFORMANCE.md`, and `docs/ACCEPTANCE.md`.
- Include exact commands and expected artifacts in doc updates so release checks stay reproducible.
