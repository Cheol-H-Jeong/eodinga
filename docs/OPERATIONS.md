# Operations Guide

`eodinga` is local-only, but it still has a few stateful paths that operators need to know when debugging packaging, launcher behavior, or stale results.

## Quick Commands

| Goal | Command | What it tells you |
| --- | --- | --- |
| Validate environment and writable paths | `eodinga doctor` | Python/runtime dependencies, writable DB path, readable roots, hotkey backend, and safe excludes |
| Inspect active runtime state | `eodinga stats --json` | active DB path, roots, counters, logging policy, log path, and crash directory |
| Check the query surface directly | `eodinga search 'query' --json` | parsed query result shape, hit count, snippets, and elapsed time |
| Rebuild once | `eodinga index --rebuild` | rebuilds the staged index and atomically swaps it into place |
| Resume live updates | `eodinga watch` | starts the watchdog-backed live-update path for the current DB |

## Default Paths

| Surface | Linux default | Windows default |
| --- | --- | --- |
| Config file | `~/.config/eodinga/config.toml` | `%APPDATA%\\eodinga\\config.toml` |
| Index database | `~/.local/share/eodinga/index.db` | `%LOCALAPPDATA%\\eodinga\\index.db` |
| Runtime log file | `~/.local/state/eodinga/logs/eodinga.log` | `%LOCALAPPDATA%\\eodinga\\logs\\eodinga.log` |
| Crash logs | `~/.local/state/eodinga/crashes/` | `%LOCALAPPDATA%\\eodinga\\crashes\\` |
| Packaging dry-run review | `packaging/dist/` in the repo | `packaging/dist/` in the repo |

`eodinga` treats indexed roots as read-only inputs. Runtime writes stay in the config, data, log, and crash locations above.

## Overrides

Use CLI flags when you want a one-off path override for a command invocation:

- `--config PATH`: read config from a non-default file.
- `--db PATH`: read or rebuild a non-default index database.
- `--log-level LEVEL`: change stderr and file-log verbosity for the current invocation.

Use env vars when you need observability output to go somewhere else:

| Variable | Effect |
| --- | --- |
| `EODINGA_LOG_PATH` | writes the rotating file log to a non-default path |
| `EODINGA_CRASH_DIR` | writes `crash-<ts>.log` files to a non-default directory |
| `EODINGA_DISABLE_FILE_LOGGING=1` | disables the file sink and keeps stderr logging only |
| `EODINGA_LOG_ROTATION` | overrides the log rotation policy |
| `EODINGA_LOG_RETENTION` | overrides how many rotated logs are kept |
| `EODINGA_LOG_COMPRESSION` | compresses rotated log files with the named codec |

`eodinga stats --json` reports the resolved `db_path`, `log_path`, `crash_dir`, and file-logging policy, so use that command after setting overrides instead of assuming they took effect.

## Symptom Runbook

| Symptom | First command | What to check next |
| --- | --- | --- |
| Expected file is missing | `eodinga search 'query' --json` | verify the query shape, then retry with a simpler filename/path-only query |
| Search results look stale | `eodinga stats --json` | confirm the active DB path, then run `eodinga watch` or `eodinga index --rebuild` |
| Startup reports recovery work | `eodinga doctor` | confirm the live DB path is writable and staged sidecars are gone after startup |
| Launcher hotkey or popup looks wrong | `eodinga doctor` | inspect the detected hotkey backend, then reopen `eodinga gui` and check launcher settings |
| CLI or GUI crashed | `eodinga stats --json` | inspect the reported `crash_dir`, then open the newest `crash-*.log` |
| Packaging dry run failed | `python packaging/build.py --target windows-dry-run` | inspect `packaging/dist/`, then run the matching Linux dry run and workflow lint |

## Recovery Notes

- Startup resumes interrupted staged rebuilds from `.index.db.next`.
- Startup also resumes interrupted recovery swaps from `.index.db.recover`.
- If SQLite left a live `-wal` sidecar behind, recovery is replayed into a staged copy before the live DB is swapped.
- `eodinga doctor` is the fastest way to see whether the runtime can still read config, open the DB path, and inspect configured roots cleanly.

## Packaging Review

When a packaging audit fails, review `packaging/dist/` before changing docs or installer inputs blindly.

1. Run the matching dry run from `docs/ACCEPTANCE.md`.
2. Inspect the rendered manifest or staged payload summary under `packaging/dist/`.
3. Compare the staged docs payload with `README.md`, `docs/ACCEPTANCE.md`, and `docs/man/eodinga.1`.
4. Re-run the dry run only after the first mismatch is fixed.
