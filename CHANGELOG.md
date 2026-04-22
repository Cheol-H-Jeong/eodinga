# Changelog

## 0.1.31 - 2026-04-23

- Switched relative `date:` filters (`today`, `yesterday`, `this-week`, `this-month`) to local timezone day boundaries instead of UTC midnight windows, so end-to-end query results now match the user’s machine clock around day rollover.
- Hardened scoped search roots across platforms by preserving Windows-style `C:/...` roots in the CLI and matching both slash styles in executor scoping, which restores `--root` filtering against native Windows path rows.
- Added regression coverage for local-day date semantics, Windows-style scoped search in both executor and CLI paths, and aligned the end-to-end date integration fixture with the local-time query contract.

## 0.1.30 - 2026-04-23

- Tightened stale-WAL startup recovery so `open_index()` now fails fast when SQLite replay cannot clear non-empty recovery sidecars, instead of reopening the index in an ambiguous state.
- Extended `eodinga doctor` to report stale-WAL recovery failure explicitly and return a failing exit code when the database still needs manual repair.
- Added focused storage and diagnostics regressions for unrecovered WAL sidecars and the fail-fast startup path, keeping the round green at the targeted reliability boundary.

## 0.1.29 - 2026-04-23

- Fixed watcher coalescing for chained same-root renames so late deletes for intermediate paths no longer leak a bogus `deleted` event after `before -> middle -> after` bursts.
- Normalized plain Korean filename fallback matching to NFC before substring and prefix checks, which restores queries like `회의록` against decomposed Hangul filenames commonly seen on some filesystems.
- Added regression coverage for both edge cases, bringing the round gate to 213 passing tests with 4 skipped.

## 0.1.28 - 2026-04-23

- Rejected unsupported or duplicate inline regex flags at parse time, so malformed queries like `content:/todo/x` and `content:/todo/ii` now fail deterministically instead of silently degrading at execution time.
- Normalized invalid operator payloads such as `case:maybe`, `size:>tenM`, `date:2026-01-01..bogus`, and `is:folder` into `QuerySyntaxError`, which keeps the CLI and query API on one error contract for malformed filters.
- Expanded parser, compiler, and CLI regressions with focused and property-based coverage for malformed regex flags and invalid operator values, hardening the correctness path without changing valid-query behavior.

## 0.1.27 - 2026-04-23

- Cut the plain ASCII name-query hot path back to `paths_fts` when it already returns hits, avoiding the expensive substring-scan supplement that was dominating the opt-in query-latency benchmark.
- Skipped the free-text `content_fts` probe entirely when the index has no parsed content, removing another no-value query from filename-only corpora.
- Added executor regressions proving plain `report-011` lookups avoid both the redundant scan fallback and the empty-content probe while still preserving content fallback and Korean-token coverage where needed.

## 0.1.26 - 2026-04-23

- Fixed rule matching so user include and exclude globs now evaluate against the visible alias path instead of silently resolving symlink targets first, which restores predictable excludes for symlinked or bind-mounted subtrees during traversal.
- Added walker and rules regressions for alias-path excludes, proving excluded symlink aliases are no longer emitted into the index while real sibling paths still traverse normally.
- Tightened the DSL parser to reject empty inline regex operator values such as `content://i`, and expanded hypothesis-invalid coverage so those malformed filters fail cleanly instead of compiling into empty regex terms.

## 0.1.25 - 2026-04-23

- Fixed the opt-in cold-start perf benchmark so its temporary fixture root is explicitly included during traversal instead of being dropped by the default `/tmp` safety denylist, which restores the benchmark’s coverage of the real walker plus bulk-index path.
- Recalibrated the cold-start perf gate to a 4.0k files/sec floor after rerunning the suite on the current Linux dev box, keeping the regression check useful without depending on the older 0.1.16 baseline.
- Refreshed the published install and performance docs with the current `.[all]` setup path plus fresh local measurements: about 4.3k files/sec cold start, 10.02 ms p95 name-query latency, 0.63 ms p95 content-query latency, and 0.132 s p99 watch visibility.

## 0.1.24 - 2026-04-23

- Strengthened the Windows packaging audit so `packaging/build.py --target windows-dry-run` now verifies the per-user install path, low-privilege installer settings, shortcut tasks, post-install launch action, Korean language support, and uninstall data-purge hook expected by the v0.1 packaging contract.
- Hardened the Linux AppImage dry run to audit the staged desktop entry plus the `AppRun` and launcher shims, proving the recipe launches `eodinga gui` through the packaged wrapper instead of only checking that files exist.
- Expanded packaging regression coverage so the PyInstaller spec must keep every declared runtime module in `hiddenimports` and every declared module path mapped to a real source file, reducing the risk of silent packaging drift.

## 0.1.23 - 2026-04-23

- Tightened the launcher’s keyboard-first flow so pending debounced queries are flushed before open/reveal actions fire, `Shift+Tab` can move into results, `Home`/`End` jump within the result list, and the footer now shows context-aware shortcut guidance.
- Made tray indexing state easier to read at a glance by switching the tray icon between idle and indexing modes while keeping the status text synchronized with the current indexing progress.
- Expanded GUI regression coverage for the new launcher actions, focus cycling, shortcut hints, and tray-state transitions, bringing the round gate to 190 passing tests with 4 skipped.

## 0.1.22 - 2026-04-23

- Hardened `test_no_network_in_source` so Python sources are now checked with AST-level import/call detection in addition to raw URL token scanning, which closes easy evasion paths such as split imports of `socket`, `urllib.request`, or `http.*`.
- Tightened the readonly filesystem safety contract by expanding `test_fs_readonly` to cover write-capable mode variants and to reject write-oriented filesystem calls inside `eodinga/core/fs.py`.
- Kept the round focused on reliability enforcement rather than new runtime behavior, so the existing index/search/watch paths remain unchanged while the v0.1 safety guarantees are more credibly pinned down.

## 0.1.21 - 2026-04-23

- Pushed CLI `search --root` scoping into the query executor so root-constrained searches now rank and limit within the requested subtree instead of post-filtering a lossy overfetch window.
- Persisted parsed content hashes onto `files.content_hash` during indexing, which makes `is:duplicate` work through the real writer/index/search path while still leaving empty or unparsed content out of duplicate matches.
- Expanded regression and integration coverage for scoped CLI search, writer-side content-hash persistence, and end-to-end `date`/`size`/`is:duplicate`/negation queries against an indexed filesystem tree.

## 0.1.20 - 2026-04-23

- Aligned the runtime denylist with the documented safe excludes so walker-based indexing now blocks volatile system/cache roots such as `/tmp`, `/snap`, and `%SystemRoot%` consistently with `eodinga doctor`.
- Hardened stale-WAL startup recovery to remove zero-length SQLite sidecars after replay, leaving recovered indexes clean for the next hot restart instead of carrying empty `-wal`/`-shm` files forward.
- Added missing safety and integration coverage for the denylist policy, end-to-end index/search flow, and hot-restart recovery from a copied stale-WAL snapshot, bringing the round gate to 173 passing tests with 4 skipped.

## 0.1.19 - 2026-04-23

- Fixed watcher coalescing so `created -> moved -> deleted(source)` bursts no longer leak a phantom delete for the transient source path after the create collapses onto its destination.
- Reset watcher lifecycle state on stop/start so the same `WatchService` instance can be restarted in-process and still emit new filesystem events.
- Added regression coverage for both watcher edge cases, bringing the round gate to 161 passing tests with 4 skipped.

## 0.1.18 - 2026-04-23

- Fixed walker cycle tracking so distinct hardlinked file paths are no longer collapsed just because they share an inode, while repeated directory inodes still stop traversal from re-entering the same subtree.
- Added traversal coverage for hardlinked files and aliased-directory inodes to pin the bind-mount/cycle behavior without requiring privileged fixtures.
- Tightened watcher coalescing so a rename followed by a redundant delete on the source path now stays a single move event, matching the same-root update semantics in the SPEC.

## 0.1.17 - 2026-04-23

- Normalized reversed ISO date ranges in the query compiler so `date:2026-01-03..2026-01-01` now behaves like the same inclusive window in forward order instead of returning no hits.
- Fixed path candidate collection to let substring-scan matches supplement partial `paths_fts` results, which restores Korean middle-token filename hits such as `회의록` for `프로젝트-회의록.txt` without regressing the FTS-first path.
- Expanded DSL/compiler/executor coverage for spaced operator values, inline OR parsing, reversed date windows, and Korean path-token edge cases.

## 0.1.16 - 2026-04-23

- Reduced cold-start indexing overhead by reusing each path’s discovery `lstat()` result and by removing per-directory child sorting from the walker, which now measures at about 5,130 files/sec on the current Linux dev box.
- Added walker regression coverage to prove each visited path is statted only once during traversal, protecting the cold-start path from duplicate filesystem metadata probes.
- Recalibrated the opt-in cold-start perf assertion to a 4.8k files/sec floor and refreshed the published README / `docs/PERFORMANCE.md` baseline numbers for the new measurement run.

## 0.1.15 - 2026-04-23

- Wired the Windows installer’s existing autostart checkbox to a real per-user `Run` entry and switched the generated installer name to the versioned `eodinga-<version>-win-x64-setup` form expected by the packaging contract.
- Hardened the PyInstaller packaging spec so the bundle audit now includes dynamic GUI/parser/hotkey modules plus the shipped i18n catalogs and license file.
- Added a Linux Debian packaging recipe, a `linux-deb-dry-run` target in `packaging/build.py`, and release-workflow coverage so the Linux release job now stages both AppImage and `.deb` artifacts.

## 0.1.14 - 2026-04-23

- Routed bare path/name lookups through `paths_fts` first, with a substring-scan fallback only when FTS misses entirely, so existing path-match behavior stays intact while the hot query path uses the indexed lookup.
- Short-circuited the executor’s common name-only branch so it skips the expensive per-record content-text filter pass unless the query actually includes negation, regex, path filters, or content terms.
- Refreshed the opt-in perf baseline after the query-path optimization: cold-start throughput measured 7,361 files/sec and name-only query latency dropped to p50 0.06 ms / p95 0.06 ms / p99 0.07 ms on the local dev box.

## 0.1.13 - 2026-04-23

- Made launcher match highlighting DSL-aware so free-text terms and quoted phrases still highlight even when the query also includes filters or negation.
- Tightened keyboard-first launcher flow with `Tab` into results, clearer indexing progress percentages, and tray-menu status text that mirrors current indexing state.
- Enriched launcher empty states with actionable shortcut guidance for opening hits, revealing folders, and returning to the filter without reaching for the mouse.

## 0.1.12 - 2026-04-23

- Tightened DSL fuzz coverage so whitespace-only tokens are rejected as invalid queries instead of slipping into the valid-query generator.
- Replaced the mocked `eodinga search` command with real indexed-query execution, including clean invalid-query errors and `--root` filtering on actual results.
- Added a 128-entry LRU cache for compiled query plans and expanded CLI coverage to prove `date:today`, `size:>10M`, `is:duplicate`, and negation work end-to-end against a real SQLite index.

## 0.1.11 - 2026-04-23

- Hardened staged-index replacement with explicit file and directory `fsync` calls around the atomic swap so SQLite snapshots survive power-loss style interruptions more reliably.
- Extended storage coverage to assert the durable-swap sync sequence in addition to staged-WAL checkpointing and sidecar cleanup.
- Taught `eodinga doctor` to detect and replay stale index WAL files before reporting DB health, with regression coverage for the repaired startup path.

## 0.1.10 - 2026-04-23

- Wired `eodinga gui` into the real Qt app flow so offscreen smoke now instantiates both the main window and popup launcher instead of returning a placeholder payload.
- Added shared launcher session state for recent queries and indexing progress, and surfaced that state in the popup empty state, docked Search tab, Index tab, and tray tooltip.
- Expanded GUI coverage for the offscreen CLI smoke path, shared launcher state, and indexing-status UI updates.

## 0.1.9 - 2026-04-23

- Fixed watcher event coalescing so create-then-rename bursts now collapse to the destination path instead of emitting both the transient source create and the later move.
- Preserved rename metadata when a moved file receives a follow-up modify event inside the debounce window, preventing the source path from being lost before incremental indexing runs.
- Added regression coverage for both rename-coalescing cases with real watcher activity and deterministic queue flushing.

## 0.1.8 - 2026-04-23

- Added an offscreen screenshot renderer that captures the real application and launcher surfaces into stable documentation assets.
- Expanded the README with screenshots, architecture/performance links, and a clearer DSL guide path for the v0.1 acceptance docs.
- Added `docs/ARCHITECTURE.md` and `docs/DSL.md`, and pinned the docs contract with tests so required guide sections and screenshot references stay present.

## 0.1.7 - 2026-04-23

- Hardened index replacement so staged SQLite WAL data is checkpointed into the database file before the atomic swap, leaving no stale sidecars behind at the target path.
- Expanded storage recovery coverage for WAL-backed staged databases and no-op recovery paths.
- Added a runtime safety test that exercises index, watch-event apply, and query flow while failing on any write-mode file open under indexed user roots.

## 0.1.6 - 2026-04-23

- Added end-to-end support for negated grouped query clauses such as `-(alpha | beta) ext:txt`, aligning the parser and compiler with the SPEC grammar.
- Expanded query correctness coverage with Hypothesis-driven valid DSL compilation checks and executor tests for negated groups and Korean filename searches.

## 0.1.5 - 2026-04-23

- Hardened packaging dry runs so `packaging/build.py --target windows-dry-run` now validates the Python/package version match and renders a versioned Inno Setup script into `packaging/dist/windows/`.
- Replaced the Linux AppImage placeholder with a source-backed AppDir staging recipe that emits an audit manifest and tarball during dry runs.
- Updated release-workflow coverage so Linux packaging exercises the AppImage dry run instead of reusing the Windows audit path.

## 0.1.4 - 2026-04-23

- Batched content-index upserts so bulk indexing reuses file/content row IDs without per-record lookup queries.
- Added opt-in performance tests under `tests/perf` for cold-start throughput, name query latency, content query latency, and watcher visibility latency behind `EODINGA_RUN_PERF=1`.
- Documented the current local performance baseline in `docs/PERFORMANCE.md` and linked the opt-in perf workflow from the README.

## 0.1.3 - 2026-04-23

- Improved launcher keyboard flow so the popup focuses the filter field when shown, arrow keys move into result navigation, and `Tab` returns to filtering without grabbing the mouse.
- Added clearer launcher empty states with shortcut and DSL guidance when there are no results.
- Updated launcher highlighting to mark every case-insensitive match instead of only the first occurrence.

## 0.1.2 - 2026-04-23

- Added end-to-end query support for `date:today|yesterday|this-week|this-month` as an alias for modified-time filtering.
- Added `is:duplicate` query support backed by indexed `content_hash` lookups, including schema migration coverage for existing databases.
- Expanded query tests to cover relative-date filters, duplicate detection, and negated size/duplicate combinations.

## 0.1.1 - 2026-04-23

- Repaired merge regressions in shared models, filesystem helpers, observability exports, and test fixtures so the baseline gate is green again.
- Fixed watcher event coalescing so rapid rename-then-delete sequences preserve both `moved` and `deleted` events.
- Added index storage reliability helpers for atomic database replacement and stale WAL recovery on startup.
- Added safety coverage for the no-network source policy and storage recovery behavior.

## 0.1.0 - 2026-04-23

- Added the initial packaging shell for `eodinga` across Windows and Linux.
- Added config loading and saving, a CLI surface, diagnostics, and bilingual i18n catalogs.
- Added PyInstaller, Inno Setup, AppImage, and Debian packaging assets.
- Added CI and release workflows for Ubuntu and Windows.
- Added unit coverage for config, CLI, diagnostics, i18n, packaging assets, and workflow linting.
