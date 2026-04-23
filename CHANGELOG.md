# Changelog

## 0.1.180 - 2026-04-23

- Added a shared `packaging/project_metadata.py` helper so Debian control data and packaging audits now read the same name, version, description, publisher, and Python requirement from `pyproject.toml` instead of drifting across hardcoded strings.
- Rendered the AppImage recipe through package-version and app-name templates during dry runs, and hardened the audit so `packaging/build.py` now proves the rendered recipe matches the current release metadata before packaging passes.
- Added `python packaging/build.py --target release-dry-run`, which runs the Windows, AppImage, and Debian dry-run audits as one packaging matrix and records a summary manifest under `packaging/dist/`.

## 0.1.174 - 2026-04-23

- Expanded `README.md` with a clearer shipped feature matrix, more query examples, practical CLI workflows, and a completed FAQ covering local-only behavior, recovery, parser extras, and health checks.
- Deepened `docs/ARCHITECTURE.md` with end-to-end request, query, and recovery diagrams plus a clearer explanation of why the runtime is split across `core`, `index`, `query`, and UI layers.
- Tightened `docs/CONTRIBUTING.md` and `docs/RELEASE.md` so contributor flow now calls out per-commit unit-test expectations, a recommended command order, and an explicit local tag handoff for release metadata rounds.

## 0.1.163 - 2026-04-23

- Added open-ended ISO date windows to `date:`, `modified:`, and `created:`, so queries like `date:2026-04-01..` and `created:..2026-04-23` now compile directly into one-sided timestamp predicates.
- Preserved ISO datetime precision for the same operators, so `modified:2026-04-23T09:15:30+00:00` and datetime ranges no longer collapse to whole-day matches.
- Expanded query regressions and DSL docs to cover the new open-ended and datetime-aware timestamp filters.

## 0.1.161 - 2026-04-23

- Expanded `date:` macros with `last-week` and `last-month`, and pinned their local-time behavior in compiler and executor regressions.
- Added bounded `size:` windows like `100..500K`, including reversed-range normalization and negated-range execution coverage.
- Added `is:empty` so zero-byte files and directories without indexed descendants can be queried directly from the DSL.

## 0.1.155 - 2026-04-23

- Fixed the default observability paths on macOS so rotating logs now land under `~/Library/Logs/eodinga` and crash reports follow the same platform-native log root instead of falling back to Linux-style state directories.
- Expanded `eodinga stats --json` to emit the full in-memory metrics registry, exposing all runtime counters and histograms alongside the existing summary fields and persisted index snapshot.
- Added an end-to-end observability regression that runs indexing, parser failure handling, watcher ingress, and search in one process, then proves the resulting counters and query-latency histogram are visible through the CLI stats surface.

## 0.1.149 - 2026-04-23

- Expanded the Windows PyInstaller packaging spec so hidden imports now include third-party modules discovered directly from real `import` and `from ... import ...` usage across the `eodinga/` source tree, reducing dependence on a hand-maintained list.
- Surfaced the source-derived hidden-import set in the Windows packaging audit and made `packaging/build.py --target windows-dry-run` fail if that derived contract goes empty or drops out of the final hidden-import payload.
- Added focused packaging regressions that pin the new source-derived modules, including `charset_normalizer`, `pathspec`, and `ebooklib.epub`, alongside the existing Windows dry-run coverage.

## 0.1.142 - 2026-04-23

- Expanded the Windows PyInstaller spec so packaging now auto-discovers real `eodinga.*` module imports from the source tree, including relative imports, instead of relying only on a hand-maintained runtime list.
- Hardened `packaging/build.py` dry-run validation so Windows, AppImage, and Debian packaging audits now fail fast when version sync, installer metadata, launcher shims, or shipped-doc contracts drift.
- Added packaging regressions that pin the new source-driven hidden-import discovery and the audit validators for Windows, AppImage, and Debian release inputs.

## 0.1.136 - 2026-04-23

- Added a dedicated launcher hotkey controller that binds the configured global shortcut at GUI startup, toggles the popup on the callback path, and shuts the backend down cleanly when the main window exits.
- Wired the Settings tab to show the active launcher shortcut and remap it live through the running hotkey backend, persisting successful changes back to config without restarting the app.
- Expanded the launcher desktop actions with a direct `copy name` shortcut and added a tray-level `Quit` action so the popup can now copy either the full path or basename and exit cleanly from the system tray.

## 0.1.130 - 2026-04-23

- Expanded integration coverage so one live `WatchService` can monitor multiple configured roots while `search(..., root=...)` still isolates newly indexed results to the correct root.
- Added an end-to-end live-delete regression that starts from a rebuilt on-disk index, removes a file from a real watched directory, and requires the stale hit to disappear from search within 500 ms.
- Added a multi-root hot-restart regression that reopens an existing index, proves preexisting cross-root queries still work, and verifies fresh watcher events from a reopened secondary root become searchable without a rewalk.

## 0.1.125 - 2026-04-23

- Split the launcher state and result-model helpers into a dedicated module, bringing the main launcher widget back under the repository's module-size guard without changing its runtime behavior.
- Expanded launcher keyboard flow so `Home`, `End`, `PgUp`, and `PgDn` can jump directly from the query field into results, and `Ctrl+A` now reliably returns focus to the query with the current text selected.
- Added explicit accessible names for the main tab surface and the remaining tab-level controls, extending the existing offscreen launcher accessibility work across the rest of the GUI.
- Tightened a boolean-operator fuzz strategy so generated regex literals no longer start with `-`, preventing the grammar test from accidentally emitting negation syntax instead of the intended literal term.

## 0.1.120 - 2026-04-23

- Centralized SQLite connection setup behind a shared helper that keeps the runtime PRAGMA profile consistent while explicitly reserving a 128-statement cache for index rebuilds, stale-WAL recovery, normal opens, and the opt-in perf harness.
- Cached the chunk-shaped SQL templates used by `IndexWriter` delete and content lookup paths, removing repeated placeholder-string reconstruction from watcher cleanup and content-row maintenance loops.
- Skipped duplicate parser work for repeated paths inside one `bulk_upsert()` batch, so content extraction now runs once per unique file path even if the caller provides duplicate records in the same transaction.

## 0.1.115 - 2026-04-23

- Expanded the shipped README with an explicit feature inventory, a compact DSL cheatsheet, generated-screenshot provenance, and direct links to contributor and release workflows so the top-level product contract is easier to audit.
- Added `docs/CONTRIBUTING.md` with the local setup, quality gates, scope guardrails, screenshot-refresh expectations, and targeted test-selection guidance used in this repository.
- Added `docs/RELEASE.md` plus deeper architecture diagrams and lifecycle sequences, documenting the version-pick, changelog, gate, tag, rebuild, recovery, and live-update flows behind the `0.1.x` release process.

## 0.1.110 - 2026-04-23

- Fixed launcher topmost behavior so the frameless popup now follows `launcher.always_on_top` from config instead of forcing a pinned-above-all-windows state on every run.
- Added `Alt+1` through `Alt+9` launcher quick-picks, letting the top nine visible hits open directly without moving focus out of the query field.
- Labeled the launcher window, search field, and results list with explicit accessible names and expanded the offscreen GUI regressions around the new launcher contracts.

## 0.1.104 - 2026-04-23

- Added a multi-root integration regression that rebuilds one index from two configured roots, proves both roots are persisted, and pins `search(..., root=...)` scoping against cross-root result leakage.
- Added a real watchdog-driven live-update integration test that creates a file in a temporary watched directory and requires it to become query-visible within 500 ms after event ingestion.
- Added a hot-restart integration regression that reopens an existing on-disk index, verifies preexisting queries still work, and proves the reopened connection can accept fresh watcher events without a full rewalk.

## 0.1.100 - 2026-04-23

- Added a real in-process observability registry so indexing, query execution, parser failures, and watcher ingress now increment stable counters instead of only emitting debug logs.
- Upgraded `eodinga stats --json` to report live runtime counters plus query-latency histogram data alongside the persisted index snapshot, and pinned that behavior with same-process CLI regressions.
- Added platform-aware rotating log defaults, richer `crash-<ts>.log` output, and explicit `EODINGA_LOG_PATH` / `EODINGA_CRASH_DIR` overrides so diagnostics can be redirected without patching code.

## 0.1.78 - 2026-04-23

- Tightened the Windows packaging audit so the rendered Inno installer now verifies its escaped `AppId`, template-driven `AppVersion`, and GUI uninstall icon path instead of relying on looser substring checks.
- Fixed the Inno template to keep `UninstallDisplayIcon` tied to the rendered GUI executable name, preventing installer metadata drift if the PyInstaller output name changes.
- Switched the PyInstaller spec to auto-discover literal `import_module(...)` dependencies from the `eodinga/` source tree and added regressions that pin the discovered hidden-import set alongside the existing runtime module contract.

## 0.1.76 - 2026-04-23

- Polished launcher keyboard navigation so the result list now wraps on `Up` / `Down` and supports `PgUp` / `PgDn` jumps for longer result sets, keeping the popup usable without reaching for the mouse.
- Expanded offscreen launcher regressions to pin the wrapped-selection and page-jump flows, and refreshed the shortcut hint text to advertise the stronger keyboard contract in-context.
- Updated the README launcher quick-start and hotkey docs to describe the new navigation behavior alongside the existing recent-query and reveal shortcuts.

## 0.1.75 - 2026-04-23

- Fixed negated boolean query operators so `-case:true` now restores case-insensitive matching and `-regex:true` now restores literal-term matching instead of silently behaving like their non-negated forms.
- Added compiler and executor regressions that pin the inverted semantics end to end, covering both mode compilation and actual query results against mixed-case and regex-looking filenames.
- Expanded the DSL fuzz suite with property tests that prove negated `case:` and `regex:` operators compile as semantic inverses of their positive boolean counterparts.

## 0.1.74 - 2026-04-23

- Polished launcher keyboard flow with `Alt+Up` / `Alt+Down` recent-query recall, so repeated searches no longer require retyping the last few filters during a desktop-search session.
- Added `Ctrl+L` as a direct return-to-filter shortcut from the results list, tightening keyboard-only launcher use without forcing a Tab cycle back through the popup.
- Expanded offscreen GUI regressions and README hotkey docs to pin the new launcher shortcuts and the updated empty-state guidance.

## 0.1.73 - 2026-04-23

- Added a shipped `docs/ACCEPTANCE.md` guide that turns SPEC §9 into a concrete release checklist with the exact local install, quality-gate, packaging, workflow-lint, and tagging commands used in this repository.
- Expanded the README with an acceptance quickcheck command block and linked the new guide from the docs map so release validation stops depending on tribal knowledge.
- Added documentation regressions that pin the acceptance guide and a top-level CLI contract test that proves `eodinga --help` continues to expose the seven required v0.1 subcommands.

## 0.1.72 - 2026-04-23

- Fixed watcher move normalization at watched-root boundaries so a rename that leaves a configured root now emits a `deleted` event for the source path, while a rename that enters a root emits `created` for the destination instead of leaking an out-of-root `moved` event downstream.
- Added queue-level watcher regressions for move-within-root, move-into-root, and move-out-of-root handling, pinning the per-root semantics required by the SPEC's watcher contract.
- Added end-to-end indexer regressions proving raw moved events from watchdog correctly delete rows for files leaving a root and create rows for files entering one, closing a multi-root correctness gap in incremental indexing.

## 0.1.71 - 2026-04-23

- Tightened the Windows packaging audit so the PyInstaller hidden-import contract now covers the dynamically loaded Linux hotkey backend modules (`pynput.keyboard` and `Xlib.*`) instead of only the statically imported runtime surface.
- Added a packaging regression that extracts the `import_module()` targets from `eodinga.launcher.hotkey_linux` and proves the generated Windows dry-run audit includes each of them, pinning the bundle against future launcher-backend drift.
- Added a workflow acceptance regression that runs `yamllint` over `release-windows.yml` and `release-linux.yml`, so the v0.1 release-checklist lint requirement is exercised in the normal test suite instead of relying on manual validation.

## 0.1.70 - 2026-04-23

- Hardened startup crash recovery so `open_index()` now resumes interrupted staged rebuilds from `.index.db.next` in addition to the existing staged WAL recovery flow, promoting a fully built replacement index on the next launch after a crash before the final swap.
- Extended `eodinga doctor` to run and report the same interrupted-build recovery path, keeping diagnostics aligned with runtime startup behavior instead of hiding stranded staged indexes.
- Added focused storage and doctor regressions for interrupted staged-build promotion and orphaned `.next` sidecar cleanup, pinning the new reliability path end to end.

## 0.1.69 - 2026-04-23

- Skipped the `IndexWriter` content-upsert phase entirely when no parser callback is configured, removing a guaranteed-empty pass from metadata-only indexing paths such as watcher updates and rebuilds with `content_enabled=False`.
- Added an opt-in staged rebuild benchmark to `tests/perf/test_cold_start.py`, so the SPEC §6.3 perf suite now measures the real `rebuild_index()` path alongside the lower-level walker-plus-writer throughput check.
- Refreshed `docs/PERFORMANCE.md` with the new rebuild benchmark, the additional `EODINGA_PERF_REBUILD_MIN_FPS` tuning knob, and the current local baseline: 6,059 files/sec cold start, 6,537 files/sec staged rebuild cold start, 56,222 records/sec bulk upsert, and 0.133 s watch visibility p99.

## 0.1.68 - 2026-04-23

- Batched delete and move-source cleanup inside `IndexWriter.apply_events()` so watcher-driven retirements now collapse path lookups and file deletes into chunked `IN (...)` statements instead of issuing one SQL round-trip per removed path.
- Added focused writer regressions that trace SQLite statements for multi-delete and multi-move batches, pinning both the reduced SQL shape and the preserved file-set outcome after event application.
- Refreshed the opt-in SPEC §6.3 perf baseline after rerunning `EODINGA_RUN_PERF=1 pytest -q tests/perf -s`: cold start measured 6,024 files/sec, bulk upsert 60,942 records/sec, content-query p95 0.64 ms, and watch visibility p99 0.132 s in the current Linux dev environment.

## 0.1.67 - 2026-04-23

- Tightened the DSL grammar fuzz gate so quoted phrase atoms are escaped before generation, and added an explicit regression for dangling phrase escapes to keep malformed input on the syntax-error path instead of the valid-query corpus.
- Fixed watcher coalescing for rename round-trips inside one debounce window so `A -> B -> A` now collapses to a safe `modified` event on the original path instead of emitting a self-move with identical source and destination.
- Preserved retired move-source suppression after flush for move-derived `created` and `modified` events, preventing late backend source deletes from generating ghost removals after a coalesced rename has already been applied.

## 0.1.66 - 2026-04-23

- Hardened the staged index swap path so `atomic_replace_index()` no longer deletes the live database's `-wal` and `-shm` sidecars before `os.replace()` succeeds, avoiding sidecar loss if the atomic swap itself fails.
- Added a focused storage regression that simulates a failed replace and proves the existing live database plus its sidecars survive intact while the staged database remains available for cleanup or retry.

## 0.1.65 - 2026-04-23

- Persisted launcher window geometry in config so the popup now reopens at the user's last size and screen position instead of resetting to the 640x480 default every session.
- Wired the GUI bootstrap path to pass the active config into the standalone launcher, and added focused config plus offscreen GUI regressions that prove the saved geometry survives a full close-and-reopen cycle.
- Polished tray activation so a click on the tray indicator now works as a toggle: first activation shows the launcher, second activation hides it again, with regression coverage to keep the behavior pinned.

## 0.1.64 - 2026-04-23

- Fixed the DSL phrase parser so escaped quotes (`\"`) and escaped backslashes (`\\`) now round-trip as literal phrase characters instead of prematurely terminating the query token.
- Expanded parser and executor regressions for escaped phrase queries, including end-to-end matching of literal quotes in filenames and literal backslashes in document content.
- Added a launcher-renderer regression that proves escaped quoted phrases still highlight correctly in result rows after HTML escaping.

## 0.1.63 - 2026-04-23

- Fixed Unicode-normalized `path:` filtering so decomposed Hangul filenames are no longer dropped by SQLite `LIKE` prefilters before the normalized Python record scan can validate them.
- Preserved the existing SQL fast path for ASCII-only `path:` literals, keeping common Latin-path filters indexed while routing only non-ASCII literals through the normalization-safe fallback.
- Added compiler and executor regressions for positive and negated Korean `path:` filters, pinning both NFC query to NFD path matching and exclusion behavior.

## 0.1.62 - 2026-04-23

- Fixed watcher coalescing for backends that emit `moved` plus a duplicate destination `created`, so the move keeps its `src_path` metadata and the index writer still removes the old source row instead of leaving a ghost entry behind.
- Tightened the end-to-end watch regressions around move handling with both queue-level and index-writer coverage, pinning the stale-source cleanup path after real rename activity.
- Corrected `path:` inline parsing so absolute literals such as `/tmp/ms` and `/tmp/ims` stay literal path filters instead of being misread as regex patterns with valid-looking flag suffixes, while malformed `path://` input still raises a clean syntax error.

## 0.1.61 - 2026-04-23

- Made config persistence use a staged temp file plus atomic replace, so failed or interrupted saves no longer risk truncating the live `config.toml` while updating launcher or root settings.
- Added config regressions that prove failed replace operations preserve the previous config payload and clean up temporary files instead of leaving recovery debris in the config directory.
- Tightened the safety gates by expanding the no-network audit to catch more common client libraries and connection entry points, and by extending the runtime write trap to cover `open()` and `os.open()` in addition to `Path.open()`.

## 0.1.60 - 2026-04-23

- Hardened walker directory metadata so symlink targets are classified through the read-only FS wrapper instead of direct `Path.is_dir()` syscalls, keeping traversal aligned with the SPEC's wrapper-only rule while still marking symlinked directories correctly.
- Made traversal fail soft when a directory can no longer be canonicalized during cycle detection, which lets indexing keep the current entry and skip only the broken subtree instead of aborting the walk.
- Added focused walker regressions for wrapper-backed symlink directory detection and resolve-failure descent suppression, pinning the bind-mount and disappearing-alias edge cases called out by the correctness slice.

## 0.1.59 - 2026-04-23

- Strengthened the Linux Debian packaging path so the staged `.deb` now includes the desktop entry, SVG app icon, launcher shim, license, and a compressed changelog instead of shipping only the bare command wrapper plus control metadata.
- Expanded the Debian packaging audit manifest and regression coverage to assert control fields, desktop-launch metadata, icon installation, launcher executability, and packaged docs through both dry-run and real-build targets.
- Documented the Linux packaging validation commands and the installed Debian asset surface in the README and architecture guide so the release workflow and operator docs describe the same audited package contract.

## 0.1.58 - 2026-04-23

- Fixed launcher row rendering so precomputed secondary-path highlights are now respected, which keeps GUI result rows aligned with the query engine's actual path matches instead of recomputing and potentially losing those spans.
- Added a launcher regression that proves `Enter` and `Ctrl+Enter` work while focus stays in the filter field, so keyboard-only open and reveal flows no longer depend on moving focus into the result list first.
- Added a renderer regression for `highlighted_path` so the launcher keeps honoring pre-highlighted containing-folder text in future UI rounds.

## 0.1.57 - 2026-04-23

- Cached recurring executor SQL shapes for record fetches, FTS candidate reads, scan fallbacks, and content backfill queries so launcher-style repeated searches stop rebuilding identical statement text on every call.
- Added executor regressions that prove repeated name and content searches reuse those cached SQL builders, keeping the optimization pinned at the unit level instead of relying on incidental perf numbers.
- Made the opt-in SPEC §6.3 perf suite configurable through `EODINGA_PERF_*` environment variables, refreshed `docs/PERFORMANCE.md` with the new scaling knobs, and recorded the current local baseline: 6,082 files/sec cold start, 60,854 records/sec bulk upsert, 0.06 ms p95 name query latency, 0.63 ms p95 content query latency, and 0.132 s p99 watch visibility.

## 0.1.56 - 2026-04-23

- Tightened the no-network safety gate so it now scans the repository's text files beyond just Python and config extensions, while still ignoring generated outputs, fixtures, and binary assets that are outside the runtime policy surface.
- Hardened startup recovery hygiene by deleting orphaned `.recover-wal` and `.recover-shm` sidecars before opening the index, which prevents interrupted staged swaps from leaving stale recovery debris behind on the next launch.
- Added focused storage regressions for orphaned recovery cleanup so the startup path now proves it can reopen cleanly after partial staged-recovery artifacts are left on disk.

## 0.1.55 - 2026-04-23

- Fixed plain bare-term negation so queries like `note -launch` now exclude files whose indexed document content contains the negated term, instead of only checking filename and path text.
- Added focused executor and CLI regressions for negated bare-term searches that resolve through auto-content matching, pinning the bug at both the API and command surface.
- Added an end-to-end indexed-tree regression proving the same negation rule holds after a real filesystem crawl and content parse.

## 0.1.54 - 2026-04-23

- Polished the launcher results list so the secondary line now shows the containing folder instead of repeating the filename in the full path, which makes scan-heavy result sets easier to parse at a glance.
- Surfaced background indexing progress directly in the launcher footer while the query box is idle, so the popup no longer reads as `Idle` during an active initial crawl and now shows the processed-file count plus percentage.
- Added focused GUI regressions for the new footer state, the containing-folder secondary line, and the remaining keyboard-only actions (`Shift+Enter` for properties, `Alt+C` for copy path).

## 0.1.53 - 2026-04-23

- Synced the Windows Inno Setup template with `packaging/pyinstaller.spec` by rendering dist-folder and GUI executable names from the spec at dry-run time, which removes a silent drift path between the PyInstaller output layout and installer shortcuts, autostart, and file payload globs.
- Expanded the Windows packaging audit to verify rendered source globs, rendered GUI executable references, and the autostart registry entry against the spec-derived names.
- Added focused packaging regressions for the new executable-name metadata and tokenized Inno template so `packaging/build.py --target windows-dry-run` stays pinned to the rendered installer contract.

## 0.1.52 - 2026-04-23

- Fixed watcher coalescing so a `moved` event keeps its source path retired even after the move has already flushed, preventing late OS delete notifications from generating a second stale delete event for the old path.
- Added focused watcher regressions for flushed move-source deletes and chained flushed moves, plus an end-to-end index update test that proves the destination record survives a late delete from the original source path.

## 0.1.51 - 2026-04-23

- Made `eodinga index` perform a real one-shot rebuild into a staged SQLite database and atomically swap it into place once the walk completes, so interrupted rebuilds no longer risk replacing the live index with a partial snapshot.
- Fixed root selection reliability by treating explicitly configured roots as stronger than the global denylist, which restores indexing for valid roots located under paths like `/tmp` during tests and local scratch workflows.
- Added CLI and unit regressions for staged rebuild success, missing-root errors, and failed rebuild rollback so the new rebuild path stays pinned end to end.

## 0.1.50 - 2026-04-23

- Fixed Unicode-normalization misses in content search so explicit `content:` terms now supplement partial FTS hits with scanned content candidates instead of dropping decomposed Hangul matches once a precomposed hit exists.
- Fixed the same partial-hit gap for plain text queries that auto-search indexed content, restoring mixed NFC/NFD Korean content matches even when filename/path FTS already returned other candidates.
- Expanded query correctness coverage with executor regressions for both Unicode content fallback paths plus broader DSL fuzzing around negated operators, inline regex values, and grouped expressions.

## 0.1.49 - 2026-04-23

- Expanded the shipped documentation set with a fourth offscreen-rendered screenshot for the settings surface, plus README coverage for supported content types, recovery flow, and the docs map.
- Deepened the DSL, architecture, and performance guides with timestamp-operator coverage, startup-recovery notes, and a concrete profiling workflow for the opt-in perf suite.
- Tightened `tests/unit/test_docs_assets.py` so the screenshot gallery and core documentation sections stay pinned to the shipped product surface.

## 0.1.48 - 2026-04-23

- Resumed interrupted staged-index recovery on startup by detecting leftover `.db.recover` databases, replaying their WAL if needed, and atomically swapping them into place before normal index open proceeds.
- Added unit and hot-restart integration regressions that cover both clean staged-resume and staged-resume-with-WAL flows, so recovery survives crashes in the middle of the earlier staged replay path.
- Extended `eodinga doctor` to report whether it resumed an interrupted recovery stage before checking stale WAL state, keeping diagnostics aligned with the startup path.

## 0.1.47 - 2026-04-23

- Trimmed `IndexWriter.bulk_upsert()` overhead on the cold-start path by reusing list-backed batches instead of copying them, streaming row tuples directly into SQLite `executemany()`, and skipping `MAX(rowid)` probes when unchanged content rows do not need new FTS ids.
- Added an opt-in `tests/perf/test_bulk_upsert.py` benchmark so the isolated writer throughput path is measured alongside the existing cold-start, query-latency, content-query, and watch-latency checks.
- Refreshed `docs/PERFORMANCE.md` with the current local perf baseline after the write-path tuning round: cold-start measured 6,152 files/sec and isolated bulk upsert measured 61,103 records/sec on this Linux dev box.

## 0.1.46 - 2026-04-23

- Fixed the DSL parser so slash-prefixed `path:` filters like `path:/tmp/log` and `path:/a/b` stay literal path terms instead of being misread as inline regexes when the basename is 1-3 letters long.
- Preserved explicit inline path-regex behavior for unambiguous cases such as `path:/tmp/log/i`, so valid flag-bearing path regex filters still compile as regex terms.
- Expanded correctness coverage with targeted parser fuzzing plus unit and end-to-end search regressions for short slash-prefixed path literals.

## 0.1.45 - 2026-04-23

- Fixed metadata-only query totals so `date:*`, `size:*`, and `is:duplicate` filters now report distinct match counts from the full branch union instead of the executor's prefetch window.
- Updated `eodinga search --json` to return the total match count in `count` and the current page length in `returned`, which keeps CLI output aligned with the launcher's result totals.
- Added focused executor and CLI regressions for large metadata-filter result sets, including `is:duplicate | size:>10M` union counting and paged JSON output.

## 0.1.44 - 2026-04-23

- Fixed watcher coalescing for move-source reuse so a file that is moved away, recreated at the original path, and then deleted in the same debounce window no longer leaves behind a phantom `created` event.
- Preserved real deletes on reused paths by only suppressing late source-path delete noise when that path has not already been claimed by a new pending event.
- Added both unit and end-to-end indexing regressions for reused move-source paths, proving the watch pipeline now leaves only the true destination file in the index after the coalesced batch is applied.

## 0.1.43 - 2026-04-23

- Improved launcher result rendering so highlights now respect positive DSL operators and regex terms across filename, path, extension badge, and content-snippet targets instead of only plain free-text tokens.
- Added visible result snippets in launcher rows when the query matches indexed document text, including correct rendering of SQLite FTS snippet markers for the actual matched phrase.
- Fixed `eodinga gui` to use the configured local index by default rather than the placeholder demo backend, and added GUI regressions for real-index searches plus graceful handling of incomplete query input.

## 0.1.42 - 2026-04-23

- Added a committed `packaging/linux/appimage-builder.yml` plus a shipped Linux SVG icon so the AppImage path now has explicit recipe inputs instead of relying on shell-script-only staging.
- Hardened the AppImage staging audit to verify the recipe, desktop entry, icon payload, and `.DirIcon` are all present and aligned inside the generated AppDir.
- Added focused packaging regressions that pin the AppImage recipe fields and the richer dry-run audit contract, keeping the packaging slice measurable without changing runtime behavior.

## 0.1.41 - 2026-04-23

- Restored watcher incremental-write throughput by batching record and content upserts per flushed event batch instead of issuing a full writer round-trip for every single filesystem event.
- Completed the launcher's keyboard action path end to end by wiring popup and embedded-search-panel results to real desktop actions for open, reveal, properties, and clipboard copy.
- Added GUI regressions for launcher action wiring plus clipboard copy behavior, keeping the UX polish round pinned to concrete user-visible behavior.

## 0.1.40 - 2026-04-23

- Fixed walker traversal for symlinked roots by preserving the configured alias path during discovery and allowing descent into that root when it resolves to a directory, restoring indexing for aliased or bind-mounted root entries without re-enabling recursive child symlink traversal.
- Corrected walker records for symlinked directories so they are now tagged as both `is_symlink` and `is_dir`, which keeps `is:file` and `is:dir` query semantics aligned with the visible filesystem entry type.
- Added unit and end-to-end regressions proving symlink-root indexing, alias-path preservation, and aliased directory metadata through the real index-and-search path.

## 0.1.39 - 2026-04-23

- Hardened walker traversal against bind-mount style alias cycles by deduplicating directory expansion on canonical resolved paths as well as `(st_dev, st_ino)`, which prevents repeated subtree re-entry when the same directory is surfaced under a different device/inode view.
- Normalized non-regex text query literals to NFC before compiling SQL and FTS clauses, restoring decomposed Korean `path:` and `content:` searches against the NFC-heavy filenames and parsed text stored in the index.
- Added focused walker and executor regressions for canonical alias-cycle traversal plus decomposed-Hangul query behavior, including snippet preservation for Korean content matches.

## 0.1.38 - 2026-04-23

- Fixed the query engine so `regex:true` now promotes plain free-text terms into validated path/name regex filters instead of silently falling back to literal substring search.
- Corrected regex-only branch execution to keep scanning ordered records until it has enough real matches, which restores late-alphabet hits that previously vanished behind the executor's initial candidate window.
- Added focused compiler, executor, and CLI regressions for regex-mode execution, large-window regex scans, and invalid regex error reporting so the query contract stays pinned end to end.

## 0.1.37 - 2026-04-23

- Refreshed the offscreen documentation screenshot pipeline so the published assets now show the real search surface, launcher results, and live indexing progress instead of a thinner static capture set.
- Expanded the README quick-start, CLI, DSL, config-path, and diagnostics sections so the v0.1 install and usage contract is easier to follow from a cold start.
- Deepened `docs/ARCHITECTURE.md`, `docs/DSL.md`, and `docs/PERFORMANCE.md`, and tightened docs-asset tests so screenshot references and core guide sections do not drift from the shipped product.

## 0.1.36 - 2026-04-23

- Switched stale-WAL startup recovery to a staged-copy flow in the database directory, replaying SQLite recovery work against the staged snapshot first and atomically replacing the live index only after replay succeeds.
- Hardened failure handling for startup recovery by cleaning up temporary recovery files on both success and failure while leaving the original index plus sidecars untouched if replay cannot be completed.
- Added focused storage regressions for staged stale-WAL replay, pre-swap atomicity, and recovery-file cleanup so the reliability path is exercised through both direct recovery and `open_index()` startup.

## 0.1.35 - 2026-04-23

- Reduced content-index write churn during bulk upserts by preserving existing file content hashes, reusing prior FTS rowids for changed documents, skipping no-op rewrites when parsed content is unchanged, and batching stale FTS row deletes instead of deleting one row at a time.
- Removed a repeated `content_map` presence probe from steady-state searches on the same SQLite connection by caching whether indexed content exists until that connection performs another write.
- Refreshed the opt-in perf baselines after rerunning `EODINGA_RUN_PERF=1 pytest -q tests/perf -s`: cold start measured about 5,988 files/sec, name/path query latency stayed at 0.06 ms p95, content query latency measured 0.62 ms p95, and watch visibility measured 0.133 s p99.

## 0.1.34 - 2026-04-23

- Tightened the Windows packaging contract by exposing the expected CLI and GUI dist names in `packaging/pyinstaller.spec`, requiring the cross-platform watchdog and `shiboken6` hidden imports, and auditing that the rendered Inno `Source` entries still match those bundle names.
- Added a Windows release-workflow validation step so `release-windows.yml` now runs `packaging/build.py --target windows-dry-run` before the packaging job, catching spec or installer drift earlier in CI.
- Fixed the AppImage audit target to report real build vs dry-run mode correctly, added non-dry-run Linux package wrapper targets in `packaging/build.py`, and routed both AppImage and Debian release packaging through that single wrapper entrypoint.

## 0.1.33 - 2026-04-23

- Polished the launcher’s keyboard-first flow so `Up` from the query jumps straight to the last hit, `Down` still enters the list from the top, and selection now stays anchored to the same file when a refined query keeps that result visible.
- Tightened match rendering by skipping negated free-text terms in UI highlights and adding an extension badge to each launcher row, making the result list closer to the v0.1 launcher contract without touching query semantics.
- Made the tray indicator actionable by wiring click and double-click activation to show the launcher, while keeping focused offscreen regressions for tray-triggered launcher open, launcher navigation, and highlight behavior.

## 0.1.32 - 2026-04-23

- Reset `WatchService` lifecycle state on `stop()`, clearing pending coalesced events and draining stale queued notifications so a reused watcher instance cannot replay pre-stop filesystem events after restart.
- Ignore duplicate `start(root)` calls for the same watched path, preventing redundant observer startup and same-root double registration inside a single process.
- Added focused watcher regressions for stale restart events and duplicate root registration, keeping the correctness round pinned to concrete lifecycle failures instead of broad refactors.

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
