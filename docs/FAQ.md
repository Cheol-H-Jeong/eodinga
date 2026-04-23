# FAQ

This guide expands the short answers in `README.md` into operator-facing details for the `0.1.x` lexical-search release.

## Search And Indexing

### Does `eodinga` send file contents anywhere?

No. The runtime is local-only, `tests/safety/test_no_network.py` enforces the source-level no-network contract, and indexed roots are treated as read-only inputs.

### Do I need parser extras for basic filename search?

No. Filename and path indexing work without parser extras. Install `.[parsers]` only when you want content extraction for supported document formats such as PDF, Office files, EPUB, HTML, or HWP.

### Why does search still return hits for unsupported file types?

Because filename and path search are always available. Unsupported or malformed documents fall back to metadata-only indexing instead of disappearing from the result set entirely.

### How does `is:duplicate` work?

It is content-hash based. Files with the same indexed content hash are grouped as duplicates; files without parsed content or a stable hash may still only match by name or path.

### Is semantic search included?

No. `0.1.x` is lexical only. Query behavior comes from the DSL, SQLite/FTS5, and the shared ranker; there is no cloud ranking, OCR, or embedding service in this line.

## Live Updates And Recovery

### What happens if indexing is interrupted?

Startup resumes interrupted staged rebuilds and interrupted recovery swaps automatically. If recovery still looks suspicious after reopen, run `eodinga doctor` and then `eodinga index --rebuild`.

### When do I need `eodinga watch`?

Use it when you want CLI-driven live updates after the initial index build. `eodinga index` is a one-shot crawl; it does not keep monitoring for later filesystem changes.

### What should I check when results look stale?

Use this order:

1. `eodinga stats --json` to confirm which database path the current surface is using.
2. `eodinga doctor` to validate writable config and database paths plus the detected hotkey backend.
3. `eodinga watch` for steady-state live updates or `eodinga index --rebuild` for a one-shot repair.

### Which files are skipped by default?

System and cache paths such as `/proc`, `/sys`, `/dev`, `/tmp`, `$HOME/.cache`, `C:\Windows`, and `%SystemRoot%` stay excluded unless the user explicitly opts in.

## Launcher And Config

### Where do pinned queries come from?

From the `launcher.pinned_queries` list in `config.toml`. The launcher also keeps a short recent-query history so you can recall earlier searches with `Alt+Up` and reuse pinned chips without retyping.

### Which commands are most useful for a quick health check?

Use `eodinga doctor` for dependency and writable-path checks, `eodinga stats --json` for the active database and counters, and `eodinga search 'query' --json` when you want scriptable result inspection.

### Where are config and index data stored?

- Linux defaults: `~/.config/eodinga/config.toml` and `~/.local/share/eodinga/index.db`
- Windows defaults: `%APPDATA%\eodinga\config.toml` and `%LOCALAPPDATA%\eodinga\index.db`

Override either path with `--config` or `--db` for one command invocation.

## Packaging And Release Review

### Where do I inspect packaging outputs before a release?

Use `packaging/dist/`. Each packaging dry run writes its audit manifests or staged payload summaries there so the release review can inspect generated inputs without running the installer.

### Does uninstall delete my local index automatically?

No by default. The Windows installer preserves `%LOCALAPPDATA%\eodinga\` unless the uninstall flow explicitly chooses purge.

### Where is the CLI reference for packaged builds?

Use `docs/man/eodinga.1`. It is generated from `eodinga.__main__._build_parser()`, so it stays aligned with `eodinga --help` instead of drifting as hand-written prose.

### Which docs should I read before cutting a release?

Use this order:

1. `docs/ACCEPTANCE.md` for the one-command gate and release checklist.
2. `docs/RELEASE.md` for the local tag and handoff workflow.
3. `docs/PERFORMANCE.md` only if you reran the opt-in perf suite in the same round.

