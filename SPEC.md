# eodinga — instant lexical file search (Everything-class)

Version: 0.1.0
Last updated: 2026-04-23

## 1. Product in one line

> Instant, always-on file search for Windows + Linux. Lexically indexes **every file on your machine** — filenames, extensions, paths, **and the full text content of document files (PDF/HWP/Office/text/code/markdown)**. Typing in the launcher returns matches in **< 30 ms**. Changes to the filesystem are reflected **within 500 ms** via OS-native change notifications. 100% on-device, no network.

Benchmark target: **Everything** (voidtools.com). Match its interactive feel. Expand it with document-content search.

Semantic/LLM search is explicitly **v0.2** — not in scope here. This SPEC is v0.1 lexical only.

## 2. Non-negotiables

1. **Cold-start**: first full index of a 1 TB SSD with ~1 M files completes in **< 15 min on a 2023 mid-range laptop**; incremental stays under 5 % CPU at idle.
2. **Query latency** (filename-only query, already indexed): **p95 ≤ 30 ms** on any query from 1 char to 100 chars against a 1 M-entry index.
3. **Document-content query latency**: **p95 ≤ 150 ms** against an index of ≥ 100 K parsed documents totaling ≥ 5 GB of text.
4. **Live update latency** (file created/renamed/moved/deleted): **≤ 500 ms** from OS event to query result change, **p99 ≤ 2 s**.
5. **Memory**: resident set **≤ 400 MB** for an indexed 1 M-entry / 100 K-document workload, idle.
6. **100% on-device**: no HTTP call anywhere in the runtime. Enforced by `test_no_network_in_source`.
7. **Read-only**: the indexer MUST NOT modify, move, copy, or delete any user file, ever. Enforced by a filesystem syscall audit test.
8. **Safe by default**: never indexes OS/system/root-owned areas unless explicit opt-in (`C:\Windows`, `/proc`, `/sys`, `/dev`, `/snap`, `$HOME/.cache`, etc. — baked-in denylist).

## 3. Scope

### 3.1 In (v0.1)

- Lexical filename + path search with substring, prefix, whole-word, regex, case-sensitive toggle.
- **Content search** inside documents: txt, md, csv, json, log, rtf, html, source code (py/js/ts/go/rs/java/c/cpp/cs/sh/sql/...), PDF, DOCX, PPTX, XLSX, HWP.
- Real-time FS watcher: one per configured root. Windows `ReadDirectoryChangesW` via `watchdog`, Linux `inotify`.
- Filters: extension, size range, mtime range, path glob include/exclude.
- Operators in query DSL: `ext:pdf`, `path:projects`, `size:>10M`, `modified:today`, `content:"exact phrase"`, `case:`, `regex:`, negation with `-`, AND by space, OR with `|`, grouping with `()`.
- Results: virtualized list, paged at 200, total-count shown, sort by name/size/mtime/path/match-score.
- **Global hotkey launcher**: `Ctrl+Shift+Space` default, configurable. Pops a compact always-on-top search window regardless of focused app. Esc hides. Enter opens top result.
- Result actions: open file, open containing folder, copy path, copy filename, "show properties", context-menu integration on the host shell.
- Multi-root: user adds any number of root paths, each with its own include/exclude rules.
- Settings GUI (PySide6): add/remove roots, hotkey remap, exclude patterns, theme, index stats, pause/resume indexing.
- Tray icon: index status, quick-search, pause indexing, exit.
- **Persistence**: index survives restart. First run does a full walk; subsequent runs do a quick consistency check (mtime + size) then go live.
- CLI: `eodinga index [--root PATH]`, `eodinga search "query"`, `eodinga watch`, `eodinga stats`, `eodinga gui`, `eodinga doctor`, `eodinga version`.
- Observability: local counters (files indexed, queries served, query latency histogram). Never uploaded.
- i18n: ko + en GUI strings.
- Windows installer (Inno Setup, real build on GitHub Actions `windows-latest`).
- Linux: AppImage + `.deb`.

### 3.2 Out (explicitly deferred to v0.2+)

- Semantic/embedding search.
- LLM-based query rewriting.
- Cloud sync of index.
- Browser-history / clipboard / screenshot-OCR ingest.
- Tag/bookmark layer.
- Cross-machine search.

## 4. Architecture

### 4.1 Modules (each is independently implementable — parallel Codex assignment)

| # | Module | Package path | Parallelizable | Depends on |
|---|---|---|---|---|
| A | FS walker (cold-start full enumeration) | `eodinga.core.walker` | yes | — |
| B | Real-time watcher | `eodinga.core.watcher` | yes | — |
| C | Path denylist + user include/exclude rules | `eodinga.core.rules` | yes | — |
| D | Parser registry + per-extension parsers | `eodinga.content.{base,text,pdf,office,hwp,code,...}` | yes (per-parser) | — |
| E | SQLite index schema + migrations (FTS5 + meta tables) | `eodinga.index.schema` | yes | — |
| F | Indexer write path (bulk + incremental) | `eodinga.index.writer` | yes | E, D |
| G | Query DSL parser + compiler → SQL | `eodinga.query.dsl` | yes | E |
| H | Query executor + ranker (RRF of name/path/content hits) | `eodinga.query.executor` | yes | E, G |
| I | Global hotkey service | `eodinga.launcher.hotkey` | yes | — |
| J | Launcher window (compact popup UI) | `eodinga.gui.launcher` | yes | H |
| K | Main GUI (roots, settings, stats) | `eodinga.gui.app` + `eodinga.gui.widgets.*` | yes | — |
| L | Config + persistence paths | `eodinga.config` | yes | — |
| M | CLI entry point | `eodinga.__main__` | yes | most |
| N | Observability (counters, rotating log) | `eodinga.observability` | yes | — |
| O | Doctor (diagnostics) | `eodinga.doctor` | yes | most |
| P | Packaging (PyInstaller + Inno + AppImage + GH Actions) | `packaging/*`, `.github/workflows/*` | yes | M, K |
| Q | Tests (unit + perf + e2e) | `tests/` | yes | all |

### 4.2 Data flow

```
         +------------------+         +----------------+
roots -->|  FS walker (A)   |-------->|  Indexer (F)   |
         +------------------+         |                |
                                      | + Parser (D)   |
         +------------------+         |                |
 events->|  Watcher  (B)    |-------->|                |
         +------------------+         +-------+--------+
                                              |
                                        writes into
                                              v
                                      +---------------+
                                      | SQLite (E)    |
                                      |  files        |
                                      |  content_fts  |
                                      |  paths_fts    |
                                      |  meta         |
                                      +-------+-------+
                                              |
                                       queries|
                                              v
         +----------------+            +--------------+
  input->| DSL parser (G) |----------->| Executor (H) |--> results
         +----------------+            +--------------+
                                              ^
                                              |
                                    +---------+---------+
                                    | Launcher UI (I,J) |  Main GUI (K)
                                    +-------------------+
```

### 4.3 Storage

SQLite file at:
- Linux: `$XDG_DATA_HOME/eodinga/index.db` (fallback `~/.local/share/eodinga/`)
- Windows: `%LOCALAPPDATA%\eodinga\index.db`

Schema (normative):

```sql
-- Core file table (one row per filesystem entry, including directories)
CREATE TABLE files (
  id           INTEGER PRIMARY KEY,
  root_id      INTEGER NOT NULL REFERENCES roots(id),
  path         TEXT NOT NULL,          -- absolute path
  parent_path  TEXT NOT NULL,
  name         TEXT NOT NULL,          -- basename
  name_lower   TEXT NOT NULL,          -- for case-insensitive prefix
  ext          TEXT NOT NULL,          -- lowercase, without dot; "" for no ext
  size         INTEGER NOT NULL,
  mtime        INTEGER NOT NULL,       -- unix seconds
  ctime        INTEGER NOT NULL,
  is_dir       INTEGER NOT NULL CHECK (is_dir IN (0,1)),
  is_symlink   INTEGER NOT NULL CHECK (is_symlink IN (0,1)),
  content_hash BLOB,                   -- 16-byte blake2b prefix; NULL for dirs / unparsed
  indexed_at   INTEGER NOT NULL,
  UNIQUE(path)
);
CREATE INDEX idx_files_name_lower_prefix ON files(name_lower COLLATE BINARY);
CREATE INDEX idx_files_ext ON files(ext);
CREATE INDEX idx_files_mtime ON files(mtime);
CREATE INDEX idx_files_size ON files(size);
CREATE INDEX idx_files_parent ON files(parent_path);

CREATE TABLE roots (
  id      INTEGER PRIMARY KEY,
  path    TEXT UNIQUE NOT NULL,
  include TEXT,                         -- JSON list of globs
  exclude TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  added_at INTEGER NOT NULL
);

-- Full-text on filenames + paths (supports Korean via unicode61 + tokenchars)
CREATE VIRTUAL TABLE paths_fts USING fts5(
  name, parent_path, path,
  content='files', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2 tokenchars '._-/'"
);

-- Full-text on parsed document content
CREATE VIRTUAL TABLE content_fts USING fts5(
  title, head_text, body_text,
  content='',
  tokenize="unicode61 remove_diacritics 2 tokenchars '._-'"
);
CREATE TABLE content_map (
  file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  fts_rowid INTEGER NOT NULL UNIQUE,
  parser   TEXT NOT NULL,
  parsed_at INTEGER NOT NULL,
  content_sha BLOB NOT NULL
);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

Journal mode `WAL`, `synchronous=NORMAL` for bulk writes (flipped to `FULL` on idle). `mmap_size=1 GiB`. `temp_store=MEMORY`. `cache_size=-64000` (64 MiB).

### 4.4 Indexer algorithm

**Cold-start (per root):**
1. Walker does an `os.scandir`-based BFS, yielding `(stat, path)` batches of 8 192.
2. Each batch goes to the indexer thread which inserts into `files` in a single transaction (`executemany`) and populates `paths_fts` via the automatic content-rowid trigger.
3. For files whose extension matches a parser, the indexer enqueues a **content parse job** on a process-pool (N = cpu_count - 1, max 8) bounded by a memory-backed queue (max 1 024 jobs, backpressure).
4. Parsed content is inserted into `content_fts` + `content_map` in transactions of 256 rows.
5. Progress emitted to observability every 5 000 files.

**Watcher:**
1. Per-root `watchdog.observers.Observer` with recursive handler.
2. Events are **debounced** (100 ms per path) and **coalesced** (create+modify = create; create+delete = noop).
3. Batches flushed every 100 ms or on 500-event threshold — whichever first.
4. Move within same root → single UPDATE path. Move across roots → DELETE+INSERT.
5. Delete cascades through `ON DELETE CASCADE` to `content_map`; then a post-flush `DELETE FROM content_fts WHERE rowid IN (...)` cleans the virtual table.

**Parser job (in worker process):**
- Opened with a **10 s wall-clock timeout** and **300 MB peak RSS cap** (`resource.setrlimit` on Linux; Windows via a subprocess wrapper with job-object memory limit).
- Returns `ParsedContent(title, head_text, body_text, content_sha)` where `body_text` capped at **1 MB per file**.
- On timeout/error: file still indexed at the name/path level; `content_map` row not created; error counter incremented.

### 4.5 Query engine

DSL grammar (EBNF, handled by a recursive-descent parser in `eodinga/query/dsl.py`):

```
query      := or_expr
or_expr    := and_expr ("|" and_expr)*
and_expr   := term (WS+ term)*
term       := [-] (op_expr | group | phrase | word | regex)
group      := "(" or_expr ")"
op_expr    := OPNAME ":" op_value
OPNAME     := ext | path | size | modified | created | is | content | case | regex
op_value   := word | phrase | size_literal | date_literal
phrase     := '"' /[^"]+/ '"'
word       := /[^\s()|"]+/ 
regex      := "/" /.../ "/" [flags]
size_literal := ("<"|">"|"<="|">="|"=")? NUMBER ("B"|"K"|"M"|"G"|"T")?
date_literal := "today" | "yesterday" | "this-week" | "this-month" | ISO8601 | ISO8601".." ISO8601
```

Executor builds a compound query:
- **Name/path hit set**: against `paths_fts` if user query has textual terms; falls back to `LIKE` prefix on `name_lower` for 1-char queries.
- **Content hit set**: against `content_fts` if user used `content:` operator or (v0.1 optional, configurable) on every query.
- **Meta filters**: pushdown to `files` WHERE clauses (ext, size, mtime, path LIKE).
- **Ranking**: Reciprocal Rank Fusion across name-match, path-match, content-match (weights 0.6 / 0.25 / 0.15 by default). Boost prefix-on-filename hits. Deboost hits in `node_modules`, `.git`, etc., if not excluded.
- **Limit**: default 200, user configurable. Total-count via `SELECT COUNT` on the same plan (short-circuit at 10 000).

All query SQL **prepared and parameterized**. No string concat. LRU cache of compiled queries (128 entries).

### 4.6 Parsers

Registered via entry points in `pyproject.toml` group `eodinga.parsers`. Each parser exports:

```python
@dataclass(frozen=True)
class ParserSpec:
    name: str
    extensions: frozenset[str]
    max_bytes: int = 50 * 1024 * 1024
    parse: Callable[[Path, int], ParsedContent]  # (path, max_body_chars) -> content
```

Built-in parsers in v0.1:
- `text` — txt, md, log, csv, json, yaml, toml, ini, cfg, rtf (charset detection via `charset-normalizer`)
- `code` — py, js, ts, tsx, jsx, go, rs, java, kt, swift, c, cc, cpp, h, hpp, cs, rb, php, scala, sh, bash, zsh, sql, lua, r
- `html` — html, htm, xml, svg (text extraction via `selectolax` or stdlib html.parser fallback)
- `pdf` — pypdf primary, `pdfminer.six` fallback
- `docx` — python-docx
- `pptx` — python-pptx
- `xlsx` — openpyxl (first 100 rows of first 5 sheets)
- `hwp` — olefile + `hwp5txt` CLI (opt-in if hwp5txt in PATH)
- `epub` — ebooklib

Parser process pool uses a **pickle-free** dispatch — workers receive `(parser_name, path, max_body_chars)` and look up the parser locally to avoid passing callables.

### 4.7 Global hotkey

`eodinga.launcher.hotkey` abstracts over platform:
- Windows: `ctypes.windll.user32.RegisterHotKey` with a background thread running a hidden message loop (`PeekMessageW`).
- Linux: `python-xlib` if `$DISPLAY` present, else `evdev` fallback, else a best-effort `pynput` backend.
- macOS: out of scope for v0.1 (declared non-goal in §3.2).

On Windows, default combo `Ctrl+Shift+Space` (MOD_CONTROL | MOD_SHIFT | VK_SPACE). Configurable via Settings; hot-rebind without restart.

### 4.8 Launcher window

- Frameless, always-on-top `QWidget` with shadowed rounded container.
- 640 × 480 default, resizable; pos/size persisted.
- Single `QLineEdit` with 16 pt font for query.
- Virtualized `QListView` beneath with file-name, secondary path line, ext badge, size, mtime, match highlight.
- **Keyboard-first**: Up/Down navigate, Enter opens, Ctrl+Enter opens containing folder, Shift+Enter shows properties, Alt+C copies path, Esc hides.
- Debounced 30 ms after last keystroke before query fires — matches Everything's feel.
- Hit-count + elapsed-ms shown bottom-right in small font.
- Empty state: recent queries + indexing progress.

### 4.9 Main GUI

Tabs: **Roots**, **Index** (stats, rebuild, vacuum), **Search** (same as launcher, docked), **Settings** (hotkey, theme, excludes), **About**.

### 4.10 CLI

```
eodinga index [--root PATH] [--rebuild]         # foreground cold-start
eodinga watch                                   # run daemon (indexer + watcher + hotkey)
eodinga search "query" [--json] [--limit N] [--root PATH]
eodinga stats [--json]
eodinga gui
eodinga doctor
eodinga version
```

Global flags: `--log-level`, `--config`, `--db PATH`.

### 4.11 Configuration

`$XDG_CONFIG_HOME/eodinga/config.toml` (Linux) / `%APPDATA%\eodinga\config.toml` (Windows). Schema via pydantic v2:

```toml
[general]
theme = "system"
language = "auto"

[launcher]
hotkey = "ctrl+shift+space"
debounce_ms = 30
max_results = 200

[index]
db_path = "~/.local/share/eodinga/index.db"
content_enabled = true
parser_timeout_s = 10
parser_max_bytes = 52428800
parser_workers = 0       # 0 = auto (cpu_count - 1, max 8)

[[roots]]
path = "/home/cheol"
include = ["**/*"]
exclude = ["**/node_modules/**", "**/.git/**", "**/__pycache__/**"]
```

Default excludes baked into code and cannot be disabled without `--i-know-what-im-doing`: `/proc`, `/sys`, `/dev`, `/snap`, `/run`, `/var/cache`, `/var/lib/docker`, `/tmp`, `$HOME/.cache`, `$HOME/.local/share/Trash`, `$HOME/snap`, `C:\Windows`, `C:\$Recycle.Bin`, `%SystemRoot%`.

## 5. Non-functional requirements

- Python 3.11+. `from __future__ import annotations` everywhere.
- No module > 500 lines (split).
- Pydantic v2 for all config and message schemas. Loguru for logs.
- Zero `print()` in library code.
- All file paths via `pathlib.Path`.
- 100 % of FS syscalls go through a thin wrapper `eodinga.core.fs` that explicitly has only read-access operations — no `rename`, `unlink`, `write`, `copy` exported. Enforced by `test_fs_wrapper_has_no_write_ops`.

## 6. Testing

### 6.1 Unit

Per module (A–O) at least:
- Walker: happy path, permission-denied fallthrough, symlink loop guard, denylist honored.
- Watcher: create/modify/move/delete events coalesced; batch flush timing.
- Rules: glob compile, default denylist merge.
- Each parser: happy + malformed fixture.
- Schema: migration from empty; FTS triggers fire; `ON DELETE CASCADE` works.
- Writer: bulk-insert 10 000 fake files under 2 s locally; incremental applies under 50 ms per event.
- DSL parser: every grammar rule + error cases + fuzz (hypothesis).
- Executor: ext filter, size range, date range, boolean, phrase, regex, negation, RRF ranking sanity.
- Hotkey: platform dispatch selector (mocked).
- Launcher UI: offscreen smoke; debounce; result navigation; match highlight.
- GUI: all tabs instantiate offscreen.
- Doctor: reports expected blocks.
- Config: round-trip save/load; migration.
- Observability: latency histogram merges correctly.

### 6.2 Integration

- End-to-end: build a 5 000-file synthetic tree including mixed doc types, index, run 20 canned queries, assert expected file in top-3.
- Watcher integration: run daemon against a tmp tree, create/rename/delete files, assert query results update within 500 ms.
- Hot-restart: index, close, reopen, assert no re-walk and queries still work.

### 6.3 Performance

- `perf_cold_start_1m_files.py`: generate 1 M empty files in tmp (real FS), measure walker+indexer throughput. Target ≥ 70 K files/sec on this reference box.
- `perf_query_latency.py`: issue 10 000 random queries against a 1 M-file index, p50/p95/p99 printed, gate at p95 ≤ 30 ms name-only.
- `perf_content_query.py`: 100 K parsed docs (5 GB synthetic corpus), p95 ≤ 150 ms.
- `perf_watch_latency.py`: create N files, measure event-to-query-visible latency; gate at p99 ≤ 2 s.

### 6.4 Safety

- `test_fs_wrapper_has_no_write_ops` — grep `eodinga/core/fs.py` exports.
- `test_no_network_in_source` — grep whole tree for `http`, `https`, `requests`, `urllib.request.urlopen`, `socket.socket`, except in explicitly-annotated `# noqa: eodinga-no-network` sites (none allowed in v0.1).
- `test_default_denylist_blocks_system_paths`.
- `test_runtime_never_writes_user_files` — mock open in "w" mode, assert none under a user-root during an index+watch+query run.

### 6.5 Target counts

≥ 80 tests green. ruff clean, pyright 0 errors, offscreen GUI smoke green, perf gates documented (may be opt-in via `EODINGA_RUN_PERF=1`).

## 7. Packaging

- `pyproject.toml` with extras: `gui` (PySide6 + pyqt resource tools), `parsers` (pypdf, pdfminer.six, python-pptx, python-docx, openpyxl, olefile, selectolax, ebooklib), `hotkey` (platform deps — `pywin32` on Windows, `python-xlib`/`evdev`/`pynput` on Linux), `dev`, `all`.
- Windows: Inno Setup `.iss` producing `eodinga-0.1.0-win-x64-setup.exe`, user-level install, no UAC, Start Menu shortcut, auto-launch at login (checkbox in installer), `.autoshelf-plan` style file-assoc not applicable here (different product).
- Linux: AppImage + `.deb`.
- GitHub Actions: `ci.yml` (lint + test on Linux/Windows × py3.11/3.12), `release-windows.yml` (builds `.exe` on tag push and attaches to Release), `release-linux.yml` (builds AppImage + `.deb`).

## 8. Project layout

```
eodinga/
├── SPEC.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── .gitignore
├── .github/
│   ├── workflows/{ci.yml,release-windows.yml,release-linux.yml}
│   └── ISSUE_TEMPLATE/
├── eodinga/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── observability.py
│   ├── doctor.py
│   ├── core/
│   │   ├── fs.py              (read-only FS wrapper — enforced)
│   │   ├── walker.py
│   │   ├── watcher.py
│   │   └── rules.py
│   ├── content/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── text.py
│   │   ├── code.py
│   │   ├── html.py
│   │   ├── pdf.py
│   │   ├── office.py
│   │   ├── hwp.py
│   │   └── epub.py
│   ├── index/
│   │   ├── schema.py
│   │   ├── migrations.py
│   │   ├── writer.py
│   │   └── reader.py
│   ├── query/
│   │   ├── dsl.py
│   │   ├── compiler.py
│   │   ├── executor.py
│   │   └── ranker.py
│   ├── launcher/
│   │   ├── hotkey.py
│   │   ├── hotkey_win.py
│   │   └── hotkey_linux.py
│   ├── gui/
│   │   ├── app.py
│   │   ├── launcher.py
│   │   ├── tabs/{roots,index,search,settings,about}.py
│   │   ├── theme.py
│   │   ├── design.py          (reused tokens from autoshelf’s style)
│   │   └── widgets/{button,card,empty_state,result_item,…}.py
│   └── i18n/{ko.json,en.json,__init__.py}
├── resources/
│   ├── icons/
│   └── styles/
├── packaging/
│   ├── pyinstaller.spec
│   ├── build.py
│   ├── windows/eodinga.iss
│   └── linux/{eodinga.desktop,appimage.sh,debian/}
└── tests/
    ├── unit/{test_walker,test_watcher,test_rules,test_parsers,…}.py
    ├── integration/{test_e2e_index_search,test_watch_updates,test_hot_restart}.py
    ├── perf/{cold_start,query_latency,content_query,watch_latency}.py
    └── safety/{test_fs_readonly,test_no_network,test_denylist}.py
```

## 9. Acceptance (v0.1)

- [ ] `pip install -e .[all]` succeeds on Python 3.11 Linux.
- [ ] `eodinga --help` lists 7 subcommands.
- [ ] `pytest -q` ≥ 80 tests green (perf tests opt-in).
- [ ] `ruff check .` clean.
- [ ] `pyright --outputjson` 0 errors.
- [ ] `QT_QPA_PLATFORM=offscreen eodinga gui` smoke instantiates main window + launcher.
- [ ] End-to-end integration test green.
- [ ] `packaging/build.py --target windows-dry-run` green on Linux.
- [ ] `release-windows.yml` yamllint clean.
- [ ] README documents install + hotkey + DSL + limitations.
- [ ] Tag `v0.1.0` and publish GitHub Release.

Perf gates are informational for v0.1 (document results in CHANGELOG); promoted to blocking in v0.2.
