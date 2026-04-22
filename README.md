# eodinga

Everything-class instant file search for Windows + Linux. `eodinga` indexes filenames, paths, and supported document text on-device, keeps the index fresh with filesystem notifications, and exposes the same engine through a hotkey launcher, GUI, and CLI.

## Status

This repository tracks the `0.1.x` lexical-search release defined in `SPEC.md`. Semantic search is out of scope for this version.

## Screenshots

![Main application window](docs/screenshots/app-window.png)

![Launcher window](docs/screenshots/launcher-window.png)

## Install

### Linux

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .[dev,parsers,gui]
```

For packaged builds, use the AppImage or `.deb` artifacts produced by CI.

### Windows

- Download the latest `eodinga-0.1.x-win-x64-setup.exe` release asset.
- Install per-user with the Inno Setup wizard.
- Optionally enable auto-start at login during install.

## First Run

1. Launch `eodinga gui` or start the installed app.
2. Add one or more roots to index.
3. Keep content indexing enabled if you want document-text matches.
4. Wait for the initial cold start to finish, then use the launcher hotkey.

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

## Query DSL

- `report` : plain lexical term
- `ext:pdf invoice` : extension filter plus term
- `path:projects content:"design review"` : path and content filters
- `size:>10M modified:today` : size and date filters
- `regex:/todo|fixme/i` : regex search
- `ext:py | ext:rs` : OR
- `-path:node_modules` : negation
- `(invoice | receipt) ext:pdf` : grouping

Full DSL coverage and examples live in [docs/DSL.md](/home/cheol/projects/eodinga/docs/DSL.md).

## Hotkey

- Default launcher shortcut: `Ctrl+Shift+Space`
- `Esc` hides the launcher
- `Enter` opens the top result
- `Ctrl+Enter` opens the containing folder
- `Shift+Enter` shows file properties

## Architecture

The runtime stack is intentionally small: read-only filesystem traversal, SQLite/FTS-backed indexing, a shared DSL compiler/executor, and thin CLI/GUI surfaces. The component map and data flow are documented in [docs/ARCHITECTURE.md](/home/cheol/projects/eodinga/docs/ARCHITECTURE.md).

## Performance

Perf gates remain opt-in in v0.1, but the suite and local baseline are documented in [docs/PERFORMANCE.md](/home/cheol/projects/eodinga/docs/PERFORMANCE.md). Run them locally with:

```bash
source .venv/bin/activate && EODINGA_RUN_PERF=1 pytest -q tests/perf -s
```

Current local-dev baseline for `0.1.16`: cold start at roughly 7.1k files/sec and 50k-file name/path lookups at about 0.07 ms p95.

## Diagnostics

Run:

```bash
eodinga doctor
```

The doctor command checks Python compatibility, importable dependencies, database writability, readable roots, the detectable hotkey backend, and the default safe excludes.

## FAQ

### Does eodinga send any data over the network?

No. Runtime is local-only by design.

### Which files are skipped by default?

System and cache paths such as `/proc`, `/sys`, `/dev`, `/tmp`, `$HOME/.cache`, `C:\Windows`, and `%SystemRoot%` stay excluded unless the user explicitly opts in.

### Does uninstall delete my local index automatically?

No. The Windows installer preserves `%LOCALAPPDATA%\eodinga\` unless the uninstall flow explicitly purges it.

### Is semantic search included?

No. `0.1.x` is lexical only.

## Limitations

- Perf gates are opt-in in v0.1. Run `EODINGA_RUN_PERF=1 pytest -q tests/perf -s` for local baselines and regression checks.
- Query quality is lexical-only. There is no semantic ranking, OCR, or cloud sync in this release.
- Content search only covers the parser set bundled in `.[parsers]`; unsupported or encrypted documents fall back to filename/path-only search.
- Live indexing depends on the local watchdog backend. Very large bursty file operations may appear after the debounce window rather than instantly.

## Uninstall

### Linux

- Remove the package or AppImage.
- Delete the config and data directories if you want to purge local state.

### Windows

- Uninstall `eodinga` from Apps or the Start Menu shortcut group.
- Choose whether to purge `%LOCALAPPDATA%\eodinga\` during uninstall.

## License

MIT. See `LICENSE`.
