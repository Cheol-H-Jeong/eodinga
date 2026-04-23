# eodinga(1)

## Name

`eodinga` - local-first lexical file search for Windows and Linux

## Synopsis

```text
eodinga [--log-level LOG_LEVEL] [--config CONFIG] [--db DB] <command> ...
eodinga index [--root ROOT] [--rebuild]
eodinga watch
eodinga search [--json] [--limit LIMIT] [--root ROOT] query
eodinga stats [--json]
eodinga gui [--test-mode]
eodinga doctor
eodinga version
```

## Description

`eodinga` indexes filenames, paths, and optional parsed document text into a local SQLite/FTS5 index. The CLI exposes the same engine used by the GUI and launcher, so search behavior, diagnostics, and stats stay aligned across surfaces.

Global options:

- `--log-level LOG_LEVEL`: set the runtime logging threshold.
- `--config CONFIG`: load configuration from an explicit `config.toml` path.
- `--db DB`: use an explicit index database path instead of the configured default.

## Commands

### `index`

Build or rebuild the local index for the configured roots or for explicit `--root` paths.

Options:

- `--root ROOT`: add one root for this run; repeat to index multiple roots.
- `--rebuild`: request a staged rebuild before swapping the finished index into place.

Example:

```bash
eodinga index --root ~/projects --root ~/docs --rebuild
```

### `watch`

Start the live-update path that keeps the existing index synchronized with filesystem events.

Example:

```bash
eodinga watch
```

### `search`

Execute a lexical query against the current index and emit either JSON or a plain-text payload.

Options:

- `query`: the DSL query string to execute.
- `--json`: emit the result payload as JSON.
- `--limit LIMIT`: cap returned hits; defaults to `200`.
- `--root ROOT`: scope the query to a single indexed root.

Examples:

```bash
eodinga search 'ext:pdf content:"release checklist"' --limit 20
eodinga search 'date:this-week -path:node_modules' --json
```

### `stats`

Report index counts and runtime counters for the active database.

Options:

- `--json`: emit the full structured stats payload.

Example:

```bash
eodinga stats --json
```

### `gui`

Launch the main Qt application shell and launcher support surface.

Options:

- `--test-mode`: create the GUI in offscreen test mode and return after processing startup events.

Example:

```bash
QT_QPA_PLATFORM=offscreen eodinga gui --test-mode
```

### `doctor`

Run local environment diagnostics covering Python compatibility, importable dependencies, readable roots, writable index paths, and the available hotkey backend.

Example:

```bash
eodinga doctor
```

### `version`

Print the current application version and exit.

Example:

```bash
eodinga version
```

## Query Pointers

`search` uses the DSL documented in [DSL.md](/tmp/eodinga-parallel/worker-4/docs/DSL.md). Common filters include:

- `ext:pdf invoice`
- `path:projects content:"design review"`
- `size:100K..500K`
- `date:this-month`
- `is:duplicate`
- `regex:/todo|fixme/i`

## Files

- Linux config: `~/.config/eodinga/config.toml`
- Linux index: `~/.local/share/eodinga/index.db`
- Windows config: `%APPDATA%\eodinga\config.toml`
- Windows index: `%LOCALAPPDATA%\eodinga\index.db`

## Exit Status

- `0`: command completed successfully.
- `1`: unhandled runtime error; a crash log is written.
- `2`: invalid CLI usage or query/config validation failure.

## See Also

- [README.md](/tmp/eodinga-parallel/worker-4/README.md)
- [DSL.md](/tmp/eodinga-parallel/worker-4/docs/DSL.md)
- [ACCEPTANCE.md](/tmp/eodinga-parallel/worker-4/docs/ACCEPTANCE.md)
