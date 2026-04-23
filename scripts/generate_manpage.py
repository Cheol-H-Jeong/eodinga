from __future__ import annotations

from argparse import _HelpAction, _SubParsersAction
from pathlib import Path

from eodinga import __version__
from eodinga.__main__ import _build_parser

GLOBAL_OPTION_HELP = {
    "--log-level LOG_LEVEL": "Set the runtime log verbosity for this invocation.",
    "--config CONFIG": "Use an explicit config file instead of the platform default path.",
    "--db DB": "Use an explicit SQLite index path instead of the configured default.",
}

COMMAND_SUMMARIES = {
    "index": "Build or rebuild the on-disk index for one or more configured roots.",
    "watch": "Start the filesystem watch loop that feeds live updates into the index.",
    "search": "Run a DSL query against the current index and print matches.",
    "stats": "Print index counts plus runtime counters and histograms.",
    "gui": "Launch the Qt application or run the offscreen GUI smoke path.",
    "doctor": "Report environment, dependency, and path diagnostics as JSON.",
    "version": "Print the current eodinga version and exit.",
}

COMMAND_OPTION_HELP = {
    "index": {
        "--root ROOT": "Add one root for this run; repeat the flag to override configured roots.",
        "--rebuild": "Force a staged rebuild instead of reusing the existing index snapshot.",
    },
    "search": {
        "query": "Query string in the shared DSL used by the CLI, GUI, and launcher.",
        "--json": "Emit structured JSON instead of the default plain-text payload.",
        "--limit LIMIT": "Cap the number of returned hits after ranking.",
        "--root ROOT": "Restrict matches to one indexed root path.",
    },
    "stats": {
        "--json": "Emit the full structured stats snapshot as JSON.",
    },
    "gui": {
        "--test-mode": "Launch the GUI in test mode and exit after processing pending events.",
    },
}


def _roff(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    if escaped.startswith((".", "'")):
        escaped = r"\&" + escaped
    return escaped


def _usage_line(parser_name: str, usage: str) -> str:
    compact = " ".join(usage.strip().split())
    prefix = f"usage: {parser_name} "
    if compact.startswith(prefix):
        compact = compact[len(prefix) :]
    return compact


def _iter_visible_actions(parser) -> list[object]:
    return [
        action
        for action in parser._actions
        if not isinstance(action, (_HelpAction, _SubParsersAction))
    ]


def _option_lines(parser, command_name: str | None = None) -> list[str]:
    lines: list[str] = []
    for action in _iter_visible_actions(parser):
        names = action.option_strings or [action.dest]
        heading = ", ".join(names)
        if action.metavar:
            heading = f"{heading} {action.metavar}"
        elif action.option_strings and action.nargs != 0:
            heading = f"{heading} {action.dest.upper()}"
        help_text = action.help or ""
        if not help_text:
            if command_name is None:
                help_text = GLOBAL_OPTION_HELP.get(heading, "")
            else:
                help_text = COMMAND_OPTION_HELP.get(command_name, {}).get(heading, "")
        lines.append(".TP")
        lines.append(rf"\fB{_roff(heading)}\fR")
        lines.append(_roff(help_text))
    return lines


def render_manpage() -> str:
    parser = _build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, _SubParsersAction)
    )
    command_names = list(subparsers.choices)

    lines = [
        f'.TH EODINGA 1 "{__version__}" "eodinga {__version__}" "User Commands"',
        ".SH NAME",
        "eodinga \\- local-first instant file search for Windows and Linux",
        ".SH SYNOPSIS",
        ".B eodinga",
        _roff(_usage_line("eodinga", parser.format_usage())),
        ".SH DESCRIPTION",
        _roff(
            "eodinga indexes local filenames, paths, and supported document text, "
            "keeps the index fresh with filesystem notifications, and exposes the "
            "same engine through CLI, GUI, and launcher surfaces."
        ),
        ".SH GLOBAL OPTIONS",
        *_option_lines(parser),
        ".SH COMMANDS",
    ]

    for name in command_names:
        command_parser = subparsers.choices[name]
        lines.extend(
            [
                ".TP",
                rf"\fB{name}\fR",
                _roff(COMMAND_SUMMARIES.get(name, "")),
                _roff(_usage_line(f"eodinga {name}", command_parser.format_usage())),
            ]
        )

    lines.extend(
        [
            ".SH COMMAND DETAILS",
        ]
    )

    for name in command_names:
        command_parser = subparsers.choices[name]
        lines.extend(
            [
                f".SS {name}",
                ".B Usage",
                _roff(_usage_line(f"eodinga {name}", command_parser.format_usage())),
            ]
        )
        command_options = _option_lines(command_parser, command_name=name)
        if command_options:
            lines.append(".B Options")
            lines.extend(command_options)

    lines.extend(
        [
            ".SH EXAMPLES",
            ".TP",
            r"\fBeodinga index --root ~/projects --root ~/docs\fR",
            _roff("Build or refresh the index for multiple roots."),
            ".TP",
            r"\fBeodinga watch\fR",
            _roff("Start the live-update watcher loop against the configured index."),
            ".TP",
            r"\fBeodinga search 'date:this-week ext:md roadmap' --limit 20\fR",
            _roff("Run a CLI search using the shared query DSL."),
            ".TP",
            r"\fBeodinga search 'is:duplicate size:>10M' --json\fR",
            _roff("Inspect larger duplicate candidates with structured JSON output."),
            ".TP",
            r"\fBQT_QPA_PLATFORM=offscreen eodinga gui --test-mode\fR",
            _roff("Run the packaged GUI smoke path without requiring a visible desktop session."),
            ".TP",
            r"\fBeodinga stats --json\fR",
            _roff("Print the active index snapshot and in-memory counters as JSON."),
            ".TP",
            r"\fBeodinga doctor\fR",
            _roff("Check dependencies, writable paths, roots, and hotkey support."),
            ".SH QUERY LANGUAGE",
            _roff(
                "The shared DSL supports plain terms, quoted phrases, grouped OR branches, "
                "negation, slash-delimited regex literals, date macros such as today or "
                "last-month, size filters, and structural operators including is:file, "
                "is:dir, is:symlink, is:empty, and is:duplicate."
            ),
            _roff(
                "See docs/DSL.md for the full grammar, operator notes, and edge-case examples."
            ),
            ".SH OUTPUT",
            _roff(
                "index, watch, stats --json, and doctor emit JSON-shaped payloads suitable for "
                "scripts. search emits plain text by default and structured JSON with --json."
            ),
            ".SH ENVIRONMENT",
            _roff("QT_QPA_PLATFORM=offscreen: force the Qt GUI smoke path for headless checks."),
            _roff("EODINGA_LOG_PATH: override the rotating file-log destination."),
            _roff("EODINGA_CRASH_DIR: override where crash-<ts>.log artifacts are written."),
            _roff("EODINGA_RUN_PERF=1: enable the opt-in perf suite under tests/perf/."),
            ".SH FILES",
            _roff("Linux config: ~/.config/eodinga/config.toml"),
            _roff("Linux database: ~/.local/share/eodinga/index.db"),
            _roff(r"Windows config: %APPDATA%\eodinga\config.toml"),
            _roff(r"Windows database: %LOCALAPPDATA%\eodinga\index.db"),
            ".SH SEE ALSO",
            _roff("README.md, docs/DSL.md, docs/ACCEPTANCE.md, docs/RELEASE.md"),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "docs" / "man" / "eodinga.1"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_manpage(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
