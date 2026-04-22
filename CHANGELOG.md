# Changelog

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
