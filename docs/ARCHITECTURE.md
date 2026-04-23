# Architecture

`eodinga` is a local-first lexical search stack. The v0.1 line keeps the system deliberately small: read-only filesystem access, SQLite/FTS5 storage, a shared query engine, and thin CLI/GUI launch surfaces on top.

## Runtime Flow

1. `eodinga.core.walker.walk_batched()` enumerates roots through the read-only wrappers in `eodinga.core.fs`.
2. `eodinga.index.writer.IndexWriter` persists file metadata into `files` and mirrors searchable fields into the `paths_fts` and `content_fts` virtual tables.
3. `eodinga.core.watcher.WatchService` coalesces live filesystem events and feeds incremental updates back through the same writer.
4. `eodinga.query.dsl.parse()` and `eodinga.query.compiler.compile_query()` lower the DSL into SQLite filters plus in-memory fallback checks.
5. `eodinga.query.executor.search()` fetches candidates, merges name/path/content rankings, and returns hits to the CLI or GUI.

## End-to-End Request Path

```text
user types query / invokes CLI
    |
    v
query parser ---> compiler ---> SQLite candidate fetch ---> ranker ---> rendered result row
                    |                    |                       |
                    |                    |                       +--> launcher / GUI / CLI formatting
                    |                    |
                    |                    +--> files + paths_fts + content_fts
                    |
                    +--> in-memory fallback checks for regex, mixed path/content, and negation edges
```

## Data Flow Diagram

```text
configured roots
    |
    v
walker / watcher ---> read-only fs wrappers ---> metadata + optional parsed content
    |                                                    |
    |                                                    v
    +-------------------------------> IndexWriter ---> SQLite tables + FTS5
                                                         |
                                                         v
                                              compiler + executor + ranker
                                                         |
                                                         v
                                                 CLI / GUI / launcher
```

## Module Map

| Area | Primary modules | Responsibility |
| --- | --- | --- |
| Filesystem boundary | `eodinga.core.fs`, `eodinga.core.walker`, `eodinga.core.rules` | Enumerate roots through read-only wrappers and default excludes. |
| Index storage | `eodinga.index.schema`, `eodinga.index.storage`, `eodinga.index.writer`, `eodinga.index.reader` | Own the SQLite schema, WAL lifecycle, staged swaps, and bulk updates. |
| Query engine | `eodinga.query.dsl`, `eodinga.query.compiler`, `eodinga.query.executor`, `eodinga.query.ranker` | Parse the DSL and turn it into ranked candidate results. |
| Content extraction | `eodinga.content.*` | Parse supported document formats into searchable text. |
| UI + CLI | `eodinga.__main__`, `eodinga.gui.*`, `eodinga.launcher.*` | Expose the same engine through commands, the main window, and the hotkey launcher. |

## Storage Schema Snapshot

| Table / structure | Purpose | Key fields |
| --- | --- | --- |
| `files` | Canonical metadata row for each indexed entry | root, path, name, extension, size, timestamps, `content_hash` |
| `paths_fts` | FTS5 mirror for name and path lookups | filename, basename, relative path, root path |
| `content_fts` | FTS5 mirror for parsed document text | extracted content payload |
| `content_map` | Stable mapping between `files` rows and content FTS rows | file row id, content row id |
| `*-wal` / `*-shm` sidecars | SQLite durability and concurrent-read state | managed by SQLite and startup recovery |
| `.index.db.next` | Fully staged rebuild candidate | promoted only after validation and checkpoint |
| `.index.db.recover` | Recovery-side working copy for interrupted swap/WAL replay | atomically replaces live DB after recovery succeeds |

## Why The Pieces Are Split This Way

- `core.*` owns contact with the real filesystem so read-only guarantees stay centralized.
- `index.*` isolates SQLite lifecycle, FTS maintenance, and crash recovery from the query/UI layers.
- `query.*` keeps the DSL, SQL lowering, and ranking logic reusable across CLI, GUI, and launcher searches.
- `gui.*` and `launcher.*` stay thin enough that UI changes do not require a second search implementation.

## Documentation And Operator Surface

- `README.md` is the user-facing overview and quick-start contract for install, launcher behavior, query examples, and recovery expectations.
- `docs/DSL.md`, `docs/ACCEPTANCE.md`, `docs/RELEASE.md`, and `docs/CONTRIBUTING.md` are treated as shipped operator documentation, not incidental notes.
- `docs/man/eodinga.1` is generated from `eodinga.__main__._build_parser()` so packaged CLI help can be audited against the real argparse surface.
- `docs/screenshots/*.png` are rendered from real Qt widgets via `eodinga.gui.docs` and `scripts/render_docs_screenshots.py`.

## Index Storage

- `files` is the source-of-truth table for root membership, timestamps, size, extension, and duplicate detection via `content_hash`.
- `paths_fts` mirrors filename and path fields for fast lexical lookups.
- `content_fts` stores parsed document text when parser extras are installed.
- `content_map` keeps the FTS row IDs stable across updates so incremental reindexing does not balloon the content index.
- `eodinga.index.storage` owns WAL replay on startup and atomic staged-index replacement.

## Lifecycle Ownership

| Lifecycle | Main owner | Supporting modules | Operator-visible command or surface |
| --- | --- | --- | --- |
| Cold build | `eodinga.index.build` | `core.walker`, `index.writer`, `content.*` | `eodinga index`, GUI index controls |
| Live refresh | `eodinga.core.watcher` | `index.writer`, `core.rules` | `eodinga watch`, GUI background indexing |
| Search | `eodinga.query.executor` | `query.dsl`, `query.compiler`, `query.ranker` | `eodinga search`, launcher, GUI search tab |
| Recovery | `eodinga.index.storage` | `doctor`, `index.schema` | startup path, `eodinga doctor` |
| Diagnostics | `eodinga.doctor`, `eodinga.observability` | config, hotkey backends, storage | `eodinga doctor`, `eodinga stats --json` |

## Index Lifecycle Sequence

```text
user / startup
    |
    +--> open_index()
            |
            +--> resume .next rebuild if present
            |
            +--> resume .recover swap if present
            |
            +--> replay stale WAL into staged copy when needed
            |
            +--> open live database
```

## Startup Recovery

- `open_index()` first resumes an interrupted staged rebuild database such as `.index.db.next`, promoting the fully built replacement index on the next startup if a crash happened before the final atomic swap.
- `open_index()` first checks for an interrupted staged recovery database such as `.index.db.recover` and resumes the atomic swap before touching the live file.
- If the live database still has a non-empty `-wal` sidecar, recovery is replayed against a staged copy first; only a clean checkpointed database is swapped into place.
- `eodinga doctor` reports both resumed staged rebuild/recovery work and unrecoverable stale-WAL failures so the operator sees the same startup path the runtime takes.
- This keeps crash recovery local to the database directory and avoids mutating indexed user roots.

## Rebuild Sequence

```text
eodinga index --rebuild
    |
    +--> create staged .index.db.next
    +--> walk roots in read-only mode
    +--> bulk upsert files + FTS content
    +--> checkpoint staged database
    +--> atomic rename into live index path
    +--> remove stale sidecars
```

## Query Execution

- The DSL supports terms, phrases, regex, grouped `|` branches, and negation.
- Structured operators such as `ext:`, `path:`, `content:`, `size:`, `date:`, `modified:`, `created:`, and `is:` compile into SQLite predicates where possible.
- Regex and mixed path/content terms are finalized in Python against the candidate set so the CLI and GUI share identical behavior.
- `eodinga.query.ranker` applies reciprocal rank fusion, filename prefix boosts, and path deboosting for noisy trees such as `node_modules`.

## Query Evaluation Boundaries

| Stage | What happens there | Why it lives there |
| --- | --- | --- |
| Parse | Tokenize and build the AST from the raw query string | Syntax errors and grouping rules stay deterministic before any I/O |
| Compile | Lower supported operators into SQL and FTS probes | Cheap predicates run close to SQLite and cut candidate volume early |
| Fetch | Read candidate rows plus any needed joined metadata | Keeps one canonical record shape for CLI, launcher, and GUI |
| Fallback evaluation | Apply regex and mixed-mode checks in Python | Handles cases SQLite cannot express without diverging semantics |
| Rank | Merge path/name/content signals into final result order | Search surfaces stay consistent across every entry point |

## Query Sequence

```text
raw query string
    |
    +--> dsl.parse()
            |
            +--> AST with terms / groups / filters / regex nodes
                    |
                    +--> compiler.compile_query()
                            |
                            +--> SQL predicates + FTS probes + fallback predicates
                                    |
                                    +--> executor.search()
                                            |
                                            +--> reader fetch
                                            +--> Python fallback evaluation
                                            +--> ranker.rerank()
                                            +--> normalized result objects
```

## Observability Flow

```text
index / watch / search command
    |
    +--> observability counters + histograms
            |
            +--> eodinga stats --json
            |
            +--> rotating runtime logs / crash-<ts>.log
```

## Operational Model

- Cold start is walker-driven: discover roots, write metadata in bulk, then parse supported documents for content rows.
- Steady state is watcher-driven: coalesced filesystem events reuse the same writer path and preserve FTS row stability for changed documents.
- Search is read-only against the index: CLI, launcher, and embedded search tab all call the same compiler and executor stack.
- Packaging keeps the app local-first: no network services, no daemon dependency outside the local watchdog flow, and no writes outside config/database state.

## Live Update Sequence

```text
filesystem event
    |
    v
WatchService debounce/coalesce
    |
    v
IndexWriter.apply_events()
    |
    +--> update files rows
    +--> refresh paths_fts / content_fts rows
    +--> commit transaction
    |
    v
next query sees updated results
```

## Recovery Decision Tree

```text
startup
    |
    +--> staged rebuild present (.next)?
    |       |
    |       +--> yes: validate and promote staged database
    |
    +--> interrupted recovery present (.recover)?
    |       |
    |       +--> yes: resume swap before opening live DB
    |
    +--> stale WAL sidecar present?
            |
            +--> yes: replay into staged copy, checkpoint, atomically replace live DB
            |
            +--> no: open live DB directly
```

## Failure Boundaries

| Failure point | Expected behavior | User-visible recovery path |
| --- | --- | --- |
| Parser fails on one file | File stays indexed by name/path; parser error is counted | Inspect `eodinga stats --json` and rerun after parser updates |
| Watch burst exceeds normal pace | Events are coalesced and backpressure is applied instead of silent drop | Keep `eodinga watch` running and check watcher metrics/logs |
| Rebuild interrupted mid-swap | Staged `.next` or `.recover` state is resumed on startup | Start the app again or run `eodinga doctor` |
| Stale WAL present on startup | WAL is replayed into a staged copy before swap | Automatic at startup; rebuild only if recovery fails |
| Unsupported content format | Filename/path search still works | Install parser extras only if content extraction matters |

## Packaging Surfaces

- Editable local development targets `pip install -e .[all]` on Python 3.11.
- Linux packaging lives under `packaging/linux/` for `.deb` and AppImage recipes.
- The Debian recipe stages the launcher shim, desktop entry, SVG icon, license, and compressed changelog into the package root before emitting the audit manifest.
- Windows packaging uses `packaging/pyinstaller.spec`, `packaging/windows/eodinga.iss`, and `packaging/build.py --target windows-dry-run`.
- Documentation screenshots are rendered from the real Qt surfaces through `eodinga.gui.docs` and `scripts/render_docs_screenshots.py`.
- Release docs also ship a generated CLI man page under `docs/man/` so packaged audits can verify the command surface without importing the project interactively.

## Platform Surface Summary

| Surface | Entry point | Purpose |
| --- | --- | --- |
| CLI | `eodinga.__main__` | Indexing, watch mode, diagnostics, and scripted search. |
| Main window | `eodinga.gui.app` | Root management, diagnostics, and settings. |
| Launcher | `eodinga.gui.launcher` | Hotkey-first search with quick keyboard actions. |
| Linux packages | `packaging/linux/*` | AppImage and `.deb` dry-run and release artifacts. |
| Windows package | `packaging/windows/eodinga.iss` | Per-user installer generated from the PyInstaller build output. |

## UI Surfaces

| Surface | Primary module | Main responsibility |
| --- | --- | --- |
| CLI | `eodinga.__main__` | Exposes the seven v0.1 subcommands and top-level flags |
| Main window | `eodinga.gui.app.EodingaWindow` | Root management, settings, diagnostics, and embedded search |
| Launcher popup | `eodinga.gui.launcher.LauncherWindow` | Hotkey-first search, keyboard navigation, and result actions |
| Shared models/widgets | `eodinga.common`, `eodinga.gui.widgets.*` | Reused result payloads, search controls, preview panes, and empty states |

## Safety Boundaries

- No runtime network access is allowed; `tests/safety/test_no_network.py` enforces that at source level.
- Filesystem writes are limited to the application database/config area; the read-only wrappers prevent mutating indexed user roots.
- Performance tests exist under `tests/perf`, but they stay opt-in for v0.1 so the default gate remains deterministic on developer machines.
