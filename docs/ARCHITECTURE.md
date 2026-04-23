# Architecture

`eodinga` is a local-first lexical search stack. The v0.1 line keeps the system deliberately small: read-only filesystem access, SQLite/FTS5 storage, a shared query engine, and thin CLI/GUI launch surfaces on top.

## Runtime Flow

1. `eodinga.core.walker.walk_batched()` enumerates roots through the read-only wrappers in `eodinga.core.fs`.
2. `eodinga.index.writer.IndexWriter` persists file metadata into `files` and mirrors searchable fields into the `paths_fts` and `content_fts` virtual tables.
3. `eodinga.core.watcher.WatchService` coalesces live filesystem events and feeds incremental updates back through the same writer.
4. `eodinga.query.dsl.parse()` and `eodinga.query.compiler.compile_query()` lower the DSL into SQLite filters plus in-memory fallback checks.
5. `eodinga.query.executor.search()` fetches candidates, merges name/path/content rankings, and returns hits to the CLI or GUI.

## Surface Entry Points

```text
CLI                 GUI shell                  Launcher
 |                     |                          |
 v                     v                          v
eodinga.__main__ --> config/load -----------> query model
        |                |                          |
        +-------> open_index() <--------------------+
                         |
                         v
                 compiler + executor
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

## Index Storage

- `files` is the source-of-truth table for root membership, timestamps, size, extension, and duplicate detection via `content_hash`.
- `paths_fts` mirrors filename and path fields for fast lexical lookups.
- `content_fts` stores parsed document text when parser extras are installed.
- `content_map` keeps the FTS row IDs stable across updates so incremental reindexing does not balloon the content index.
- `eodinga.index.storage` owns WAL replay on startup and atomic staged-index replacement.

## Storage Shape

```text
files
  id, root, path, name, ext, size, created_at, modified_at, content_hash
    |                         |
    |                         +--> duplicate detection / metadata filters
    |
    +--> paths_fts(name, path)
    +--> content_map(file_id <-> content_rowid)
            |
            +--> content_fts(text)
```

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

## Query Sequence

```text
user query
   |
   v
dsl.parse()
   |
   v
compile_query()
   |
   +--> SQLite predicates for exact operators
   +--> fallback checks for regex / mixed clauses
   |
   v
executor.search()
   |
   +--> candidate fetch from files + FTS tables
   +--> reciprocal-rank fusion
   +--> snippet extraction
   |
   v
CLI JSON/text or GUI result rows
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

## Packaging Surfaces

- Editable local development targets `pip install -e .[all]` on Python 3.11.
- Linux packaging lives under `packaging/linux/` for `.deb` and AppImage recipes.
- The Debian recipe stages the launcher shim, desktop entry, SVG icon, license, and compressed changelog into the package root before emitting the audit manifest.
- Windows packaging uses `packaging/pyinstaller.spec`, `packaging/windows/eodinga.iss`, and `packaging/build.py --target windows-dry-run`.
- Documentation screenshots are rendered from the real Qt surfaces through `eodinga.gui.docs` and `scripts/render_docs_screenshots.py`.
- The CLI man page is generated from `eodinga.__main__` through `scripts/generate_man_page.py`, keeping terminal docs tied to the shipped argparse surface.

## UI Surfaces

- `eodinga.__main__` exposes the seven subcommands required by the v0.1 contract.
- `eodinga.gui.app.EodingaWindow` is the settings and diagnostics shell.
- `eodinga.gui.launcher.LauncherWindow` is the hotkey-first search surface with keyboard navigation and match highlighting.
- Both UI paths reuse the same query models from `eodinga.common`.

## Safety Boundaries

- No runtime network access is allowed; `tests/safety/test_no_network.py` enforces that at source level.
- Filesystem writes are limited to the application database/config area; the read-only wrappers prevent mutating indexed user roots.
- Performance tests exist under `tests/perf`, but they stay opt-in for v0.1 so the default gate remains deterministic on developer machines.
