# eodinga

Everything-class instant file search for Windows + Linux. `eodinga` indexes filenames, paths, and supported document text on-device, keeps the index fresh with filesystem notifications, and exposes the same engine through a hotkey launcher, GUI, and CLI.

## Status

This repository tracks the `0.1.x` lexical-search release defined in `SPEC.md`. Semantic search is out of scope for this version.

## Screenshots

![Main application window](docs/screenshots/app-window.png)

![Launcher window](docs/screenshots/launcher-window.png)

![Index progress window](docs/screenshots/index-progress.png)

![Settings window](docs/screenshots/settings-window.png)

All screenshots in this repository are rendered offscreen from the real Qt surfaces with `python scripts/render_docs_screenshots.py`; they are not mockups.

## Install

### Linux

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[all]
```

Use `.[all]` for the full v0.1 local-dev surface, including GUI, parser, hotkey, lint, and test dependencies. For packaged builds, use the AppImage or `.deb` artifacts produced by CI.
The Linux release artifacts both launch `eodinga gui`; the `.deb` also installs the desktop entry, SVG icon, and packaged changelog under `/usr/share/doc/eodinga/`.

### Windows

- Download the latest `eodinga-0.1.x-win-x64-setup.exe` release asset.
- Install per-user with the Inno Setup wizard.
- Optionally enable auto-start at login during install.

## Install Matrix

| Goal | Command or artifact | Notes |
| --- | --- | --- |
| Local development on Linux | `pip install -e .[all]` | Includes GUI, parser, hotkey, lint, and test extras. |
| CLI-only hacking | `pip install -e .[dev]` | Enough for tests and lint when you do not need parser or GUI extras. |
| Content parsing coverage | `pip install -e .[parsers]` | Adds optional document parsers on top of the base runtime. |
| Windows packaging tooling | `pip install -e .[dev,parsers,gui,packaging]` | Adds the PyInstaller toolchain used by the Windows release workflow. |
| Packaged Linux desktop install | AppImage or `.deb` artifact | Both launch the GUI; `.deb` also stages desktop metadata and packaged docs. |
| Packaged Windows desktop install | `eodinga-0.1.x-win-x64-setup.exe` | Per-user install; uninstall preserves `%LOCALAPPDATA%\\eodinga\\` unless purge is chosen. |

## First Run

1. Launch `eodinga gui` or start the installed app.
2. Add one or more roots to index.
3. Keep content indexing enabled if you want document-text matches.
4. Wait for the initial cold start to finish, then use the launcher hotkey.

## Quick Start

1. Install with `pip install -e .[all]`.
2. Open `eodinga gui`, add your project or document roots, and let the first index finish.
3. Hit `Ctrl+Shift+Space` to open the launcher anywhere.
4. Start with plain terms, then narrow with operators like `ext:pdf`, `path:docs`, `date:this-week`, or `size:>10M`.
5. Use `Enter` to open the selected result or `Ctrl+Enter` to reveal it in the file manager.
6. Use `Alt+Up` to recall recent queries, `Ctrl+L` to jump back to the filter, and `PgUp` / `PgDn` to move through longer result sets without leaving the keyboard.
7. Re-run `python scripts/render_docs_screenshots.py` if you update the Qt surfaces and want the shipped screenshots refreshed.

## Feature Overview

| Area | Included in `0.1.x` |
| --- | --- |
| Search surfaces | Shared engine across CLI, main GUI, and hotkey launcher. |
| Local-first behavior | Local-only indexing of filenames, paths, and supported document text. |
| Freshness | Real-time refresh through watchdog-backed filesystem events. |
| Query language | Terms, phrases, groups, negation, regex, path filters, size filters, date macros, and duplicate detection. |
| Content extraction | Text, source code, Office files, PDF, EPUB, HTML, and HWP when parser extras are installed. |
| Recovery | Atomic staged rebuild and startup recovery for interrupted index swaps and stale WAL state. |
| Packaging | Windows installer, Linux AppImage, and Linux `.deb` dry-run paths. |

## Feature Inventory

- Query language: plain terms, phrases, grouped OR branches, negation, regex literals, date macros, size ranges, and structural filters such as regular-file `is:file`, directory `is:dir`, or `is:duplicate`.
- Search ranking: shared lexical ranking across CLI, GUI, and launcher with filename/path/content blending plus stable tie handling.
- Content extraction: optional parser-backed indexing for Office documents, PDF, EPUB, HTML, HWP, and common text/source formats.
- Runtime freshness: staged rebuilds for cold start plus watchdog-backed incremental updates for steady-state changes.
- Operator tooling: `doctor`, `stats --json`, generated man page, screenshots rendered from real Qt widgets, and dry-run packaging audits.
- Packaging contract: Windows installer plus Linux AppImage and `.deb` paths, all documented and verified in-repo.

## Surface Matrix

| Surface | Entry point | Best for | Notes |
| --- | --- | --- | --- |
| CLI | `eodinga search`, `index`, `watch`, `stats`, `doctor` | scripted indexing, diagnostics, CI-like checks | emits plain text or `--json`; shares the same DSL and ranking engine as the GUI |
| Main GUI | `eodinga gui` | root management, settings, indexing progress, diagnostics | offscreen-rendered screenshots in this repo come from the real Qt widgets |
| Launcher | global hotkey, packaged launcher entry, embedded search tab | fast keyboard-first open/reveal flows | recent queries, pinned queries, hover preview, and quick actions stay local to the same index |
| Linux packages | AppImage / `.deb` | desktop installation on Linux | both launch the GUI surface; `.deb` also installs desktop metadata and packaged docs |
| Windows installer | Inno Setup + PyInstaller bundle | per-user install on Windows | uninstall keeps `%LOCALAPPDATA%\\eodinga\\` unless purge is chosen explicitly |

## At A Glance

- Local-only indexing and search; no hosted service and no runtime network calls.
- One query language shared by `eodinga search`, the main GUI, and the hotkey launcher.
- Filename/path search works without parser extras; `.[parsers]` extends content extraction only.
- Live refresh comes from watchdog-backed filesystem notifications rather than a polling daemon.
- The shipped release contract includes docs, screenshots, packaging dry-runs, and the generated CLI man page.

## Acceptance Quickcheck

Use this when you want to validate the shipped v0.1 surface before cutting a release:

```bash
source .venv/bin/activate && pytest -q tests && ruff check eodinga tests && pyright --outputjson | python3 -c "import sys,json; s=json.load(sys.stdin)['summary']; print('pyright', s)" && QT_QPA_PLATFORM=offscreen python -c "from eodinga.gui.app import launch_gui; launch_gui(test_mode=True)" && python packaging/build.py --target windows-dry-run && yamllint .github/workflows/release-windows.yml
```

The full SPEC §9 checklist, expected commands, and release-tag workflow live in [docs/ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md).

If the quickcheck fails, stop at the first failing command and continue with the matching recovery path from `docs/ACCEPTANCE.md` instead of retrying the whole chain blindly.

## CLI

```bash
eodinga index [--root PATH] [--rebuild]
eodinga watch
eodinga search "query" [--json] [--limit N] [--root PATH]
eodinga stats [--json]
eodinga gui
eodinga doctor
eodinga version
```

Global flags:

- `--log-level`
- `--config`
- `--db`

Typical flows:

```bash
eodinga index --root ~/projects --root ~/docs
eodinga watch
eodinga search 'ext:pdf content:"release checklist"' --limit 20
eodinga stats --json
eodinga doctor
```

## Query DSL

- `report` : plain lexical term
- `ext:pdf invoice` : extension filter plus term
- `path:projects content:"design review"` : path and content filters
- `size:>10M modified:today` : size and date filters
- `size:100K..500K date:last-month` : bounded range plus date macro
- `date:2026-04-01.. modified:..2026-04-23` : open-ended ISO ranges
- `modified:2026-04-23T09:15:30+00:00` : exact ISO datetime filter
- `date:yesterday is:duplicate` : relative date plus duplicate detection
- `is:empty -is:dir` : empty files only
- `created:2026-04-23` : creation-time filter
- `is:file -is:empty` : non-empty regular files only
- `regex:true report-\\d+` : treat plain terms as regex
- `regex:/todo|fixme/i` : regex search
- `ext:py | ext:rs` : OR
- `-path:node_modules` : negation
- `(invoice | receipt) ext:pdf` : grouping

Full DSL coverage and examples live in [docs/DSL.md](/home/cheol/projects/eodinga/docs/DSL.md).

## DSL Cheatsheet

| Goal | Query |
| --- | --- |
| Search by plain term | `roadmap` |
| Restrict by extension | `ext:pdf invoice` |
| Restrict by path | `path:projects content:"design review"` |
| Find recent files | `date:this-week` |
| Start from an ISO date | `date:2026-04-01..` |
| Stop at an ISO date | `created:..2026-04-23` |
| Match one instant | `modified:2026-04-23T09:15:30+00:00` |
| Find size ranges | `size:100K..500K` |
| Find empty files only | `is:empty -is:dir` |
| Find regular files only | `is:file` |
| Find duplicates | `is:duplicate` |
| Find the previous calendar month | `date:last-month ext:pdf` |
| Exclude noisy trees | `-path:node_modules` |
| Run regex | `regex:/todo|fixme/i` |

## Query Patterns

Use these when a search feels ambiguous and you want to force the engine down one path:

| Intent | Query | Why |
| --- | --- | --- |
| Restrict a plain term to path metadata only | `path:docs release` | keeps `release` broad while `path:` narrows the subtree |
| Require document body text | `content:"release checklist" ext:md` | avoids filename-only false positives |
| Search exact text across punctuation or newlines | `"incident review"` | quoted phrases normalize separators during fallback checks |
| Exclude an entire noisy branch | `-(path:node_modules | path:.venv) report` | group negation is clearer than repeating `-path:` |
| Run regex only on free-text terms | `regex:true report-[0-9]+ ext:md` | plain tokens become regex while structured filters stay structured |
| Keep regex scoped to one field | `content:/TODO|FIXME/i path:src` | avoids broad path/name regex scans when only content matters |

## Supported Content Types

- Plain text and source code: `.txt`, `.md`, `.py`, and similar text-first formats.
- Office documents: `.docx`, `.pptx`, `.xlsx`, plus legacy OLE-backed formats handled by the parser extras.
- Publishing formats: `.pdf`, `.epub`, `.html`, and `.hwp` when the parser dependencies are installed.
- Filename and path search still works even when a file type has no content parser or the file is malformed.

## Hotkey

- Default launcher shortcut: `Ctrl+Shift+Space`
- `Esc` hides the launcher
- `Enter` opens the top result
- `Ctrl+Enter` opens the containing folder
- `Shift+Enter` shows file properties
- `Alt+Up` / `Alt+Down` recalls recent queries
- `Up` / `Down` wraps through the result list once focus is in the list
- `PgUp` / `PgDn` jumps through longer result sets
- `Ctrl+L` returns focus to the filter field

## Common Workflows

Open the launcher, search across multiple roots, and reveal the selected hit in the file manager:

```bash
eodinga index --root ~/projects --root ~/docs && eodinga watch
```

```bash
eodinga search 'date:this-week ext:md roadmap' --limit 20
eodinga search 'regex:/todo|fixme/i path:src' --json
eodinga search 'is:duplicate size:>10M' --limit 50
```

Check runtime state when results look stale:

```bash
eodinga doctor
eodinga stats --json
eodinga index --rebuild
```

## Task Recipes

| Task | Command |
| --- | --- |
| Find documents changed this week | `eodinga search 'date:this-week ext:md' --limit 10` |
| Audit large duplicate media | `eodinga search 'is:duplicate size:>10M' --limit 50` |
| Search docs with regex | `eodinga search 'regex:/todo|fixme/i path:docs' --json` |
| Confirm runtime health | `eodinga doctor && eodinga stats --json` |
| Refresh shipped docs assets | `python scripts/generate_manpage.py && python scripts/render_docs_screenshots.py && pytest -q tests/unit/test_docs_assets.py` |

## Architecture

The runtime stack is intentionally small: read-only filesystem traversal, SQLite/FTS-backed indexing, a shared DSL compiler/executor, and thin CLI/GUI surfaces. The component map and data flow are documented in [docs/ARCHITECTURE.md](/home/cheol/projects/eodinga/docs/ARCHITECTURE.md).

## Performance

Perf gates remain opt-in in v0.1, but the suite and local baseline are documented in [docs/PERFORMANCE.md](/home/cheol/projects/eodinga/docs/PERFORMANCE.md). Run them locally with:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

Current local-dev baseline: cold start at roughly 6.0k files/sec, 50k-file name/path lookups at about 0.06 ms p95, content queries at about 0.62 ms p95, and watch visibility at about 0.133 s p99.

## Packaging

- Validate Windows packaging inputs with `python packaging/build.py --target windows-dry-run`.
- Validate Linux AppImage packaging with `python packaging/build.py --target linux-appimage-dry-run`.
- Validate Linux Debian packaging with `python packaging/build.py --target linux-deb-dry-run`.
- Audit the rendered manifests and staged payload descriptions under `packaging/dist/` after each dry run; that directory is the review surface for release packaging changes.

## Operator References

- `docs/DSL.md` is the complete query reference.
- `docs/ACCEPTANCE.md` is the release gate and shipped-surface checklist.
- `docs/ARCHITECTURE.md` covers the runtime flow, storage model, and packaging surfaces.
- `docs/PERFORMANCE.md` captures the opt-in perf suite and current local baseline.
- `docs/CONTRIBUTING.md` is the contributor workflow for sync, tests, docs refresh, and release hygiene.
- `docs/RELEASE.md` is the local release-cut and handoff procedure.
- `docs/man/eodinga.1` is the generated CLI reference derived from the real argparse surface.

## Package Artifacts

- Windows release builds emit a PyInstaller bundle plus an Inno Setup installer audit under `packaging/dist/`.
- Linux AppImage dry runs render `packaging/linux/appimage-builder.yml` from the current package version before building.
- Linux `.deb` dry runs stage the launcher, desktop entry, SVG icon, license, and compressed changelog into the package root.
- The packaged docs surface includes `README.md`, `docs/ACCEPTANCE.md`, and `docs/man/eodinga.1` as operator references for shipped builds.

## Release Handoff

1. Finish the docs, code, or packaging slice and keep each logical commit green with `pytest -q tests/unit`.
2. Run the one-command acceptance pass from `docs/ACCEPTANCE.md`.
3. Bump `pyproject.toml` and `eodinga/__init__.py`, add the new `CHANGELOG.md` entry, and create the local `v0.1.N` tag.
4. Hand off the clean branch plus local tag; rebasing, pushing, and GitHub release publication stay outside the worker round.

## Recovery and Troubleshooting

- Startup automatically resumes interrupted staged rebuilds (`.index.db.next`), interrupted recovery swaps (`.index.db.recover`), and stale SQLite WAL replay before opening the live index.
- If results look stale, run `eodinga doctor`, then `eodinga stats` to confirm the active database path before rebuilding.
- A one-shot recovery path is `eodinga index --rebuild`; live updates still require `eodinga watch` or the packaged background service flow.
- Documentation and screenshots are part of the shipped contract; refresh the gallery with `python scripts/render_docs_screenshots.py` after visible UI changes.

### Quick Runbook

| Symptom | First command | What to confirm next |
| --- | --- | --- |
| No search hits you expect | `eodinga search 'query' --json` | confirm the query shape and whether filename/path-only search would have matched |
| Results look stale after file changes | `eodinga stats --json` | verify the active database path, then run `eodinga watch` or `eodinga index --rebuild` |
| Startup mentions recovery | `eodinga doctor` | check that the live DB path is writable and recovery sidecars are gone after startup |
| Hotkey or launcher looks wrong | `eodinga doctor` | inspect detected hotkey backend and then re-open `eodinga gui` for settings/state |
| Packaging audit failed | `python packaging/build.py --target windows-dry-run` | re-run the matching Linux dry run and workflow lint from `docs/ACCEPTANCE.md` |

## Config and Data Paths

- Linux config defaults to `~/.config/eodinga/config.toml` and the index database to `~/.local/share/eodinga/index.db`.
- Windows uses `%APPDATA%\\eodinga\\config.toml` for config and `%LOCALAPPDATA%\\eodinga\\index.db` for the database.
- Override either location with `--config` or `--db` when running CLI commands.
- Runtime writes stay inside those config/database areas; indexed roots are treated as read-only inputs.

## Diagnostics

Run:

```bash
eodinga doctor
```

The doctor command checks Python compatibility, importable dependencies, database writability, readable roots, the detectable hotkey backend, and the default safe excludes.

If search looks stale, run `eodinga stats` to confirm the active database path, then either `eodinga watch` for live updates or `eodinga index --rebuild` to rebuild once.

## Operator Checklist

Use this short sequence when you need a high-signal local health check without opening the full acceptance guide:

```bash
eodinga doctor
eodinga stats --json
eodinga search 'date:this-week ext:md' --limit 10
```

If those are clean but the packaged app still looks wrong, continue with the release-gate commands in `docs/ACCEPTANCE.md`.

## Docs Map

- [docs/DSL.md](/home/cheol/projects/eodinga/docs/DSL.md): query cheatsheet and operator notes.
- [docs/ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md): SPEC §9 release checklist and validation commands.
- [docs/ARCHITECTURE.md](/home/cheol/projects/eodinga/docs/ARCHITECTURE.md): runtime flow, index lifecycle, and packaging surfaces.
- [docs/PERFORMANCE.md](/home/cheol/projects/eodinga/docs/PERFORMANCE.md): opt-in perf suite, current baselines, and profiling workflow.
- [docs/CONTRIBUTING.md](/home/cheol/projects/eodinga/docs/CONTRIBUTING.md): local workflow, guardrails, and doc/screenshot expectations for contributors.
- [docs/RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md): release-candidate workflow, tagging, packaging validation, and handoff.

## Contributing

Contributor workflow lives in [docs/CONTRIBUTING.md](/home/cheol/projects/eodinga/docs/CONTRIBUTING.md). Use it for local setup, quality gates, screenshot refreshes, and scope guardrails before opening a change.

## Release Process

Release-specific steps live in [docs/RELEASE.md](/home/cheol/projects/eodinga/docs/RELEASE.md), with [docs/ACCEPTANCE.md](/home/cheol/projects/eodinga/docs/ACCEPTANCE.md) as the short gate checklist.

## FAQ

### Does `eodinga` send file contents anywhere?

No. The runtime is local-only, the source tree is guarded by `tests/safety/test_no_network.py`, and indexed roots are treated as read-only inputs.

### What happens if indexing is interrupted?

Startup resumes interrupted staged rebuilds and recovery swaps automatically. If recovery still looks suspicious, run `eodinga doctor` and then `eodinga index --rebuild`.

### Do I need parser extras for basic filename search?

No. Filename and path indexing work without parser extras. The `parsers` extra only expands content extraction for supported document formats.

### Which commands are most useful for a quick health check?

Use `eodinga doctor` for dependency and writable-path checks, `eodinga stats --json` for the active database and counters, and `eodinga search 'query' --json` when you want scriptable result inspection.

### Why did a quoted phrase match across punctuation or line breaks?

Phrase matching normalizes separator boundaries during fallback evaluation so `"incident review"` still finds `incident-review` and `incident\nreview`. If you need exact punctuation-sensitive matching, use a regex literal instead.

### How do I tell whether a regex applied to everything or only one field?

`regex:true` changes plain free-text tokens into regex path/name terms. `content:/.../`, `path:/.../`, or a top-level `/.../` literal are explicit field-scoped regex forms and are easier to debug in shared docs or shell history.

### Where do I inspect packaging outputs before a release?

Use `packaging/dist/`. Each packaging dry run writes its audit manifests or staged output summary there so the release review can inspect generated inputs without running the installer.

### Which files are skipped by default?

System and cache paths such as `/proc`, `/sys`, `/dev`, `/tmp`, `$HOME/.cache`, `C:\Windows`, and `%SystemRoot%` stay excluded unless the user explicitly opts in.

### Does uninstall delete my local index automatically?

No. The Windows installer preserves `%LOCALAPPDATA%\eodinga\` unless the uninstall flow explicitly purges it.

### Is semantic search included?

No. `0.1.x` is lexical only.

### Where is the CLI reference for packaged builds?

Use `docs/man/eodinga.1`. It is generated from the parser in `eodinga.__main__`, so it stays aligned with `eodinga --help` instead of drifting as hand-written prose.

## Limitations

- Perf gates are opt-in in v0.1. Run `EODINGA_RUN_PERF=1 pytest -q tests/perf -s` for local baselines and regression checks.
- Query quality is lexical-only. There is no semantic ranking, OCR, or cloud sync in this release.
- Content search only covers the parser set bundled in `.[parsers]`; unsupported or encrypted documents fall back to filename/path-only search.
- Live indexing depends on the local watchdog backend. Very large bursty file operations may appear after the debounce window rather than instantly.
- Duplicate detection is content-hash based, so files without parsed content or stable hashes may only match by name/path.

## Uninstall

### Linux

- Remove the package or AppImage.
- Delete the config and data directories if you want to purge local state.

### Windows

- Uninstall `eodinga` from Apps or the Start Menu shortcut group.
- Choose whether to purge `%LOCALAPPDATA%\eodinga\` during uninstall.

## License

MIT. See `LICENSE`.
