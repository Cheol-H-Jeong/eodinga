from __future__ import annotations


def recent_snapshot_name_summary(snapshots: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for snapshot in snapshots:
        name = snapshot.get("name")
        if not isinstance(name, str) or not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def recent_snapshot_latest_at_summary(snapshots: list[dict[str, object]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for snapshot in snapshots:
        name = snapshot.get("name")
        recorded_at = snapshot.get("recorded_at")
        if not isinstance(name, str) or not name or not isinstance(recorded_at, str):
            continue
        previous = latest.get(name)
        if previous is None or recorded_at > previous:
            latest[name] = recorded_at
    return dict(sorted(latest.items()))


def command_summary(counters: dict[str, int]) -> dict[str, dict[str, int]]:
    commands: dict[str, dict[str, int]] = {}
    prefix = "commands."
    for name, value in counters.items():
        if not name.startswith(prefix) or name.startswith("commands.exit_code."):
            continue
        command_name, _, status = name[len(prefix) :].rpartition(".")
        if not command_name or status not in {"started", "completed", "failed", "interrupted"}:
            continue
        commands.setdefault(command_name, {})[status] = value
    return dict(sorted((name, dict(sorted(statuses.items()))) for name, statuses in commands.items()))


def exit_code_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "commands.exit_code."
    exit_codes = {
        name[len(prefix) :]: value for name, value in counters.items() if name.startswith(prefix)
    }
    return dict(sorted(exit_codes.items(), key=lambda item: int(item[0])))


def crash_type_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "crashes."
    crash_types = {
        name[len(prefix) :]: value
        for name, value in counters.items()
        if name.startswith(prefix)
    }
    return dict(sorted(crash_types.items()))


def parser_activity_summary(counters: dict[str, int]) -> dict[str, dict[str, int]]:
    parser_activity: dict[str, dict[str, int]] = {}
    prefix = "parsers."
    for name, value in counters.items():
        if not name.startswith(prefix):
            continue
        parser_name, _, status = name[len(prefix) :].rpartition(".")
        if not parser_name or status not in {"error", "parsed", "skipped_too_large"}:
            continue
        if status == "error":
            key = "errors"
        elif status == "parsed":
            key = "parsed"
        else:
            key = "skipped_too_large"
        parser_activity.setdefault(parser_name, {})[key] = value
    return dict(
        sorted((name, dict(sorted(statuses.items()))) for name, statuses in parser_activity.items())
    )


def watcher_event_type_summary(counters: dict[str, int]) -> dict[str, int]:
    prefix = "watcher_events."
    event_types = {
        name[len(prefix) :]: value
        for name, value in counters.items()
        if name.startswith(prefix)
    }
    return dict(sorted(event_types.items()))


def watcher_failure_summary(counters: dict[str, int]) -> dict[str, dict[str, int]]:
    return {
        "observer_cleanup": _suffix_summary(counters, "watcher_observer_cleanup_failures."),
        "observer_start": _suffix_summary(counters, "watcher_observer_failures."),
        "observer_startup_cleanup": _suffix_summary(
            counters,
            "watcher_observer_startup_cleanup_failures.",
        ),
    }


def log_sink_file_source_summary(counters: dict[str, int]) -> dict[str, int]:
    return _suffix_summary(counters, "log_sinks.file.source.")


def log_sink_file_disabled_reason_summary(counters: dict[str, int]) -> dict[str, int]:
    return _suffix_summary(counters, "log_sinks.file.disabled.")


def _suffix_summary(counters: dict[str, int], prefix: str) -> dict[str, int]:
    return dict(
        sorted(
            (name[len(prefix) :], value)
            for name, value in counters.items()
            if name.startswith(prefix)
        )
    )
