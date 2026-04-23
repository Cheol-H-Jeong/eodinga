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

## Read And Write Boundaries

| Boundary | Read from | Write to | Why it matters |
| --- | --- | --- | --- |
| Indexed user roots | configured filesystem roots | never | search targets stay read-only inputs; the runtime should not mutate indexed files |
| Runtime config | platform config path or `--config` | same config path | launcher/UI preferences and pinned queries live outside the SQLite index |
| Search index | platform data path or `--db` | same database directory plus staged sidecars | rebuilds, WAL replay, and watcher updates are isolated to the index directory |
| Derived docs assets | `eodinga.__main__`, Qt docs surfaces | `docs/man/`, `docs/screenshots/` | release docs are generated from the real runtime, not hand-maintained copies |

## Runtime Path Layout

| Path class | Typical location | Contents | How to inspect it |
| --- | --- | --- | --- |
| Config path | `~/.config/eodinga/config.toml` or `%APPDATA%\\eodinga\\config.toml` | roots, launcher options, pinned queries | `eodinga doctor` or explicit `--config` |
| Live index path | `~/.local/share/eodinga/index.db` or `%LOCALAPPDATA%\\eodinga\\index.db` | `files`, `paths_fts`, `content_fts`, WAL sidecars | `eodinga stats --json` or explicit `--db` |
| Crash/log path | platform app-data area or env override | rotating runtime log and `crash-<ts>.log` files | `EODINGA_LOG_PATH`, `EODINGA_CRASH_DIR` |
| Derived docs assets | `docs/man/`, `docs/screenshots/`, `packaging/dist/` | generated man page, screenshots, dry-run manifests | `tests/unit/test_docs_assets.py` and packaging dry runs |

The split matters operationally: when a query is wrong, first confirm which config and database paths the surface is using before assuming the parser or ranker is inconsistent.

## Module Map

| Area | Primary modules | Responsibility |
| --- | --- | --- |
| Filesystem boundary | `eodinga.core.fs`, `eodinga.core.walker`, `eodinga.core.rules` | Enumerate roots through read-only wrappers and default excludes. |
| Index storage | `eodinga.index.schema`, `eodinga.index.storage`, `eodinga.index.writer`, `eodinga.index.reader` | Own the SQLite schema, WAL lifecycle, staged swaps, and bulk updates. |
| Query engine | `eodinga.query.dsl`, `eodinga.query.compiler`, `eodinga.query.executor`, `eodinga.query.ranker` | Parse the DSL and turn it into ranked candidate results. |
| Content extraction | `eodinga.content.*` | Parse supported document formats into searchable text. |
| UI + CLI | `eodinga.__main__`, `eodinga.gui.*`, `eodinga.launcher.*` | Expose the same engine through commands, the main window, and the hotkey launcher. |

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

## SQLite Schema Snapshot

| Table or virtual table | Role in the runtime | Populated by |
| --- | --- | --- |
| `files` | canonical metadata for roots, paths, timestamps, size, and duplicate hashes | `IndexWriter.bulk_upsert()` and `IndexWriter.apply_events()` |
| `paths_fts` | lexical filename/path retrieval for fast candidate lookup | mirrored from `files` during writer commits |
| `content_fts` | parsed document-body retrieval for phrase/content queries | parser-backed content writes only |
| `content_map` | stable bridge between `files` rows and `content_fts` row ids | storage/writer coordination during content refresh |

The split lets the executor ask SQLite for cheap lexical candidates first, then run regex or mixed fallback checks in Python only on the reduced set.

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

## Recovery Artifact Meanings

| Artifact | Meaning | Expected next action |
| --- | --- | --- |
| `.index.db.next` | interrupted staged rebuild or ready-to-promote replacement index | let startup validate and promote it; rebuild only if validation fails |
| `.index.db.recover` | interrupted atomic swap or WAL-replay recovery copy | restart into `open_index()` so recovery can finish before manual cleanup |
| `index.db-wal` | live WAL sidecar with uncheckpointed SQLite work | let storage replay/checkpoint it through staged recovery rather than deleting it |
| `crash-<ts>.log` | top-level runtime failure report | inspect the exception plus the recent runtime snapshot before rerunning commands |

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

## Search Decision Path

```text
query term or operator
    |
    +--> can SQLite/FTS answer it directly?
    |       |
    |       +--> yes: compile to SQL predicate or FTS probe
    |       |
    |       +--> no: keep as Python fallback predicate
    |
    +--> fetch reduced candidate set
    |
    +--> run fallback predicates for regex / mixed path-content / negation edges
    |
    +--> fuse scores and emit normalized hits
```

## Query Consistency Contract

- `eodinga search`, the embedded search tab, and the launcher all call the same parser, compiler, executor, and ranker path.
- Root scoping, regex fallback, duplicate detection, and date/size operators are therefore release-contract behavior, not UI-only affordances.
- When operators report a mismatch between CLI and launcher results, treat it as one shared engine bug unless there is direct evidence the surfaces are reading different databases.

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

## Operator Evidence Sources

| Symptom | First evidence source | Why this is the shortest path |
| --- | --- | --- |
| wrong or stale results | `eodinga stats --json` | proves which database path the active surface is reading |
| startup recovery messages | database directory sidecars plus `eodinga doctor` | shows whether `.next`, `.recover`, or WAL replay is the active path |
| launcher/hotkey mismatch | `eodinga doctor` plus config path | confirms backend detection and launcher-specific settings before blaming query logic |
| release-doc drift | `tests/unit/test_docs_assets.py` and `packaging/dist/` | catches mismatches between runtime docs, generated assets, and packaged payloads |

## Symptom-To-Subsystem Map

| Symptom | Most likely boundary | First module or artifact to inspect |
| --- | --- | --- |
| query returns nothing but filename should match | query compiler or active DB path | `eodinga.query.compiler`, `eodinga.query.executor`, then `eodinga stats --json` |
| launcher differs from CLI for the same query | shared query engine or per-surface DB selection | `eodinga.query.*`, launcher config, active DB path |
| files changed on disk but results lag | watcher debounce or writer commit path | `eodinga.core.watcher`, `eodinga.index.writer`, watch counters |
| restart prints recovery warnings | storage recovery boundary | `eodinga.index.storage`, `.next`, `.recover`, `index.db-wal` |
| packaged docs or screenshots look stale | derived docs asset boundary | `scripts/generate_manpage.py`, `scripts/render_docs_screenshots.py`, `tests/unit/test_docs_assets.py` |
| dry run claims missing payload files | packaging boundary | `packaging/build.py`, staged manifest under `packaging/dist/` |

The map is intentionally boundary-first: confirm whether the issue is query, storage, watcher, docs, or packaging shaped before digging into implementation details.

## Documentation Asset Flow

```text
runtime surface changes
    |
    +--> README / docs/*.md edits
    |
    +--> scripts/generate_manpage.py ------> docs/man/eodinga.1
    |
    +--> scripts/render_docs_screenshots.py -> docs/screenshots/*.png
    |
    +--> tests/unit/test_docs_assets.py
```

- `README.md` is the short contract; the deeper guides under `docs/` explain why the runtime is shaped the way it is.
- `scripts/generate_manpage.py` derives the shipped man page from `eodinga.__main__._build_parser()` so CLI help and packaged docs stay aligned.
- `scripts/render_docs_screenshots.py` renders offscreen Qt widgets through `eodinga.gui.docs`, keeping screenshots tied to real UI state instead of mock assets.
- `tests/unit/test_docs_assets.py` pins the presence of the shipped sections and checks that the derived man page still matches the checked-in artifact.

## Derived Asset Ownership Matrix

| Derived asset | Source of truth | Refresh command | Why it matters |
| --- | --- | --- | --- |
| `docs/man/eodinga.1` | `eodinga.__main__._build_parser()` | `python scripts/generate_manpage.py` | keeps the packaged CLI reference derived from argparse instead of hand-edited prose |
| `docs/screenshots/*.png` | `eodinga.gui.docs` Qt surfaces | `python scripts/render_docs_screenshots.py` | proves the documented UI and keyboard flow still exist on real widgets |
| `packaging/dist/*` audit outputs | `packaging/build.py` dry-run targets | `python packaging/build.py --target ...-dry-run` | turns installer and package claims into reviewable artifacts instead of assumptions |

- The release workflow depends on these generated assets because prose alone cannot prove that the CLI, GUI, and packaging surfaces still match the current code.
- Treating them as first-class architecture outputs keeps docs-only rounds aligned with the same derivation boundaries as runtime changes.

## Release Input Map

```text
runtime code / CLI / UI changes
    |
    +--> README.md + docs/*.md
    |
    +--> generated man page / screenshots
    |
    +--> packaging dry-run manifests in packaging/dist/
    |
    +--> acceptance gate + local tag
```

- The release flow treats documentation, generated assets, and packaging manifests as part of the same shipped surface.
- This is why docs-only rounds still run `tests/unit/test_docs_assets.py` and the matching dry-run or GUI smoke command instead of stopping at markdown edits.

## Release Input Dependency View

```text
README / docs change
    |
    +--> docs-assets contract test
    |
    +--> derived asset refresh when CLI or UI changed
    |       |
    |       +--> docs/man/eodinga.1
    |       +--> docs/screenshots/*.png
    |
    +--> packaging dry-run when shipped artifact claims changed
            |
            +--> packaging/dist/* manifest review
```

- A README edit that changes install or package wording is not "just prose"; it changes the claimed release surface and therefore depends on packaging evidence.
- A docs-only round can stay theme-scoped while still touching real runtime evidence because the generated man page and screenshots are derived directly from code.

## Release Failure Isolation

| Failure signal | First owner to inspect | Typical repair scope |
| --- | --- | --- |
| `tests/unit/test_docs_assets.py` fails | README or `docs/*.md` contract | headings, links, stale examples, or missing generated-doc references |
| GUI smoke no longer matches docs/screenshots | `eodinga.gui.*` plus `docs/screenshots/*.png` | refresh screenshots or fix the described UI path |
| packaging dry run contradicts docs | `packaging/build.py`, `packaging/linux/*`, or `packaging/windows/*` | staged payload metadata, artifact naming, bundled docs list |
| version or changelog mismatch | release metadata files only | final metadata commit and local tag retarget |

- This keeps release debugging narrow: start at the contract that failed instead of re-running the entire gate blindly.
- The same isolation rule applies to docs-only rounds, where the failing evidence usually points directly at one derived asset family.

## Narrowing Order

1. Prove the active config or DB path if the symptom is runtime-facing.
2. Prove the derived docs asset if the symptom is documentation-facing.
3. Prove the staged packaging manifest if the symptom is release-facing.
4. Only then widen to full test, GUI smoke, or packaging sweeps.

This order keeps operators from mutating settings or rerunning broad gates before they know which boundary actually drifted.

## Docs-Only Change Path

```text
docs edit
    |
    +--> docs-assets contract test
    |
    +--> regenerate man page or screenshots if the documented surface moved
    |
    +--> GUI smoke and matching packaging dry-run
    |
    +--> metadata commit + local tag
```

- A docs-only round still crosses runtime boundaries because screenshots, the generated man page, and packaging manifests are derived from the real codebase.
- That is why a docs change can stay in the `docs` theme while still requiring evidence from Qt smoke or packaging dry-run paths.

## State Ownership

| State | Owner | Why it lives there |
| --- | --- | --- |
| Indexed file metadata | `files` table | Canonical root/path/timestamp/size state for every query surface. |
| Lexical path lookup | `paths_fts` | Fast candidate generation for filename and path matches. |
| Parsed document text | `content_fts` + `content_map` | Stable full-text rows for content phrases and parser-backed search. |
| Runtime settings | config file under platform app dirs | Keeps user-visible launcher/gui behavior outside the index. |
| Derived docs assets | `docs/man/` and `docs/screenshots/` | Versioned release inputs audited by tests instead of ad-hoc notes. |

## Operational Model

- Cold start is walker-driven: discover roots, write metadata in bulk, then parse supported documents for content rows.
- Steady state is watcher-driven: coalesced filesystem events reuse the same writer path and preserve FTS row stability for changed documents.
- Search is read-only against the index: CLI, launcher, and embedded search tab all call the same compiler and executor stack.
- Packaging keeps the app local-first: no network services, no daemon dependency outside the local watchdog flow, and no writes outside config/database state.

## Failure Domains

- Walker failures should stay scoped to the current root entry; unreadable files are skipped without widening writes outside the index path.
- Writer and storage failures are handled at the database boundary so startup recovery can reason about `.next`, `.recover`, and stale WAL artifacts explicitly.
- Query fallback failures must not mutate state; they only affect one search invocation and are observable through `eodinga stats --json` and runtime logs.
- Docs or packaging drift is treated as a release-input failure, caught by `tests/unit/test_docs_assets.py` and the packaging dry-run audits before a tag is cut.

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

## Watch-To-Query Sequence

```text
filesystem change
    |
    +--> watchdog event
            |
            +--> WatchService debounce/coalesce
                    |
                    +--> IndexWriter.apply_events()
                            |
                            +--> SQLite commit
                                    |
                                    +--> next CLI / GUI / launcher query sees the new row set
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

## Packaging Surfaces

- Editable local development targets `pip install -e .[all]` on Python 3.11.
- Linux packaging lives under `packaging/linux/` for `.deb` and AppImage recipes.
- The Debian recipe stages the launcher shim, desktop entry, SVG icon, license, and compressed changelog into the package root before emitting the audit manifest.
- Windows packaging uses `packaging/pyinstaller.spec`, `packaging/windows/eodinga.iss`, and `packaging/build.py --target windows-dry-run`.
- Documentation screenshots are rendered from the real Qt surfaces through `eodinga.gui.docs` and `scripts/render_docs_screenshots.py`.
- Release docs also ship a generated CLI man page under `docs/man/` so packaged audits can verify the command surface without importing the project interactively.

## Packaging Review Path

1. Run the matching `packaging/build.py --target ...-dry-run` command.
2. Inspect the emitted manifest or staged payload summary under `packaging/dist/`.
3. Compare the staged docs payload with `README.md`, `docs/ACCEPTANCE.md`, and `docs/man/eodinga.1`.
4. Cut the local tag only after the dry-run output and shipped docs agree.

## Release Evidence Sequence

```text
docs/runtime change
    |
    +--> tests/unit/test_docs_assets.py
    |
    +--> GUI smoke or packaging dry-run evidence
    |
    +--> packaging/dist/ manifest review
    |
    +--> version bump + changelog + local tag
```

- The architecture of the release process mirrors the runtime split: docs contract first, derived/runtime evidence second, metadata last.
- This keeps the local tag attached to a tree whose docs, generated assets, and staged packaging outputs have already been checked together.

## Platform Surface Summary

| Surface | Entry point | Purpose |
| --- | --- | --- |
| CLI | `eodinga.__main__` | Indexing, watch mode, diagnostics, and scripted search. |
| Main window | `eodinga.gui.app` | Root management, diagnostics, and settings. |
| Launcher | `eodinga.gui.launcher` | Hotkey-first search with quick keyboard actions. |
| Linux packages | `packaging/linux/*` | AppImage and `.deb` dry-run and release artifacts. |
| Windows package | `packaging/windows/eodinga.iss` | Per-user installer generated from the PyInstaller build output. |

## UI Surfaces

- `eodinga.__main__` exposes the seven subcommands required by the v0.1 contract.
- `eodinga.gui.app.EodingaWindow` is the settings and diagnostics shell.
- `eodinga.gui.launcher.LauncherWindow` is the hotkey-first search surface with keyboard navigation and match highlighting.
- Both UI paths reuse the same query models from `eodinga.common`.

## Safety Boundaries

- No runtime network access is allowed; `tests/safety/test_no_network.py` enforces that at source level.
- Filesystem writes are limited to the application database/config area; the read-only wrappers prevent mutating indexed user roots.
- Performance tests exist under `tests/perf`, but they stay opt-in for v0.1 so the default gate remains deterministic on developer machines.

## Operator Debug Path

```text
reported issue
    |
    +--> runtime query problem?
    |       |
    |       +--> eodinga stats --json
    |       +--> eodinga doctor
    |
    +--> docs or screenshot mismatch?
    |       |
    |       +--> tests/unit/test_docs_assets.py
    |       +--> regenerate man page / screenshots if needed
    |
    +--> packaging or installer mismatch?
            |
            +--> packaging/build.py --target ...-dry-run
            +--> inspect packaging/dist/
```

- The debug path starts with evidence already produced by the architecture: config/database state, generated docs assets, or staged packaging manifests.
- If one branch proves clean, move to the neighboring boundary instead of broadening the same check.

When an operator reports stale or surprising results, the shortest architecture-aware path is:

1. `eodinga stats --json` to confirm which database the active surface is reading.
2. `eodinga doctor` to validate writable database/config paths and the detected hotkey backend.
3. `eodinga watch` or `eodinga index --rebuild` depending on whether the issue is live-update lag or a one-shot recovery need.

That sequence mirrors the architecture itself: active DB selection, environment validation, then either watcher-driven incremental repair or staged rebuild.
