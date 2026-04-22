# Contributing

This repository keeps the `0.1.x` line intentionally small: local-first runtime behavior, lexical search, measurable release increments, and strict quality gates. Contributions should preserve that shape.

## Development Loop

1. Create or refresh a Python 3.11 virtualenv.
2. Install the editable local surface with `pip install -e .[dev,parsers,gui]`.
3. Make the smallest coherent change you can defend.
4. Run the narrowest useful tests first, then the shared gate before handing work off.

Typical local loop:

```bash
source .venv/bin/activate
pytest -q tests/unit
ruff check eodinga tests
pyright
```

Use `pytest -q tests` when you are touching shared runtime behavior, GUI flows, packaging, or docs that are already pinned by integration tests.

## Scope Rules

- Do not edit `SPEC.md`.
- Keep runtime local-only: no network dependencies, no writes outside config and database areas.
- Preserve the read-only contract for indexed roots.
- Prefer targeted changes over broad refactors; measurable progress beats speculative cleanup.
- Keep modules under 500 lines when practical.

## Testing Expectations

- `pytest -q tests/unit` should stay green after each logical commit.
- Run `ruff check eodinga tests` and `pyright` before handing off a round.
- Use the focused perf suite only when the change is performance-related: `EODINGA_RUN_PERF=1 pytest -q tests/perf -s`.
- If you change visible Qt surfaces, refresh the shipped screenshots with `python scripts/render_docs_screenshots.py`.

## Docs And Screenshots

- README is part of the shipped contract, not optional polish.
- Keep `docs/ARCHITECTURE.md`, `docs/PERFORMANCE.md`, and `docs/RELEASE.md` aligned with the current repository behavior.
- When UI behavior changes, regenerate screenshots from the real Qt surfaces instead of editing static images by hand.

## Commit And Release Hygiene

- Use Conventional Commits.
- Bump the patch version in `pyproject.toml` and `eodinga/__init__.py` for each release round.
- Add the round summary to the top of `CHANGELOG.md`.
- Create the local release tag only after the gate is green.

## Packaging Notes

- Windows packaging is validated with `python packaging/build.py --target windows-dry-run`.
- Linux packaging is validated with `python packaging/build.py --target linux-appimage-dry-run` and `python packaging/build.py --target linux-deb-dry-run`.
- Release workflow details live in `docs/RELEASE.md`.
