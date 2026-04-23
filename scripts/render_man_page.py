from __future__ import annotations

import argparse
from pathlib import Path

from eodinga.__main__ import _build_parser

SECTION = "1"
DATE = "2026-04-23"
TITLE = "eodinga"

COMMAND_DESCRIPTIONS = {
    "index": "build or rebuild the local search index",
    "watch": "report the configured watch surface for live index updates",
    "search": "run a lexical query against the local index",
    "stats": "print index and in-process observability counters",
    "gui": "launch the Qt desktop UI and hotkey surface",
    "doctor": "run local environment and index diagnostics",
    "version": "print the current eodinga version",
}

EXAMPLES = [
    "eodinga index --root ~/projects --root ~/docs",
    "eodinga search 'date:this-week ext:md roadmap' --limit 20",
    "eodinga search 'regex:/todo|fixme/i path:src' --json",
    "eodinga stats --json",
    "eodinga doctor",
]


def _roff(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("-", "\\-")
    return escaped.replace('"', '\\"')


def _iter_options(parser: argparse.ArgumentParser) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            continue
        if not action.option_strings:
            continue
        option = ", ".join(action.option_strings)
        if action.metavar:
            option = f"{option} {action.metavar}"
        elif action.nargs != 0 and action.dest not in {"help"}:
            option = f"{option} {action.dest.upper()}"
        description = action.help or ""
        options.append((option, description))
    return options


def _command_parsers(
    parser: argparse.ArgumentParser,
) -> list[tuple[str, argparse.ArgumentParser]]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices.items())
    return []


def render_man_page() -> str:
    parser = _build_parser()
    commands = _command_parsers(parser)
    lines = [
        f'.TH "{TITLE.upper()}" "{SECTION}" "{DATE}" "{TITLE} {TITLE} manual"',
        ".SH NAME",
        f"{TITLE} \\- everything-class instant file search for Windows and Linux",
        ".SH SYNOPSIS",
        ".B eodinga",
        "[\\fIglobal options\\fR] \\fIcommand\\fR [\\fIcommand options\\fR]",
        ".SH DESCRIPTION",
        (
            "\\fBeodinga\\fR indexes local filesystem metadata and optional parsed document "
            "content, then exposes the same lexical search engine through the CLI, GUI, and "
            "launcher surfaces. The runtime is local-only; indexed roots are treated as "
            "read-only inputs."
        ),
        ".SH GLOBAL OPTIONS",
    ]
    for option, description in _iter_options(parser):
        lines.extend([".TP", f"\\fB{_roff(option)}\\fR", _roff(description)])

    lines.extend([".SH COMMANDS"])
    for name, subparser in commands:
        usage = " ".join(subparser.format_usage().split()).replace("usage: ", "")
        lines.extend(
            [
                ".TP",
                f"\\fB{name}\\fR",
                f"{_roff(COMMAND_DESCRIPTIONS.get(name, ''))}. Usage: {_roff(usage)}",
            ]
        )

    for name, subparser in commands:
        lines.extend([f'.SH "{name.upper()} COMMAND"', ".PP", _roff(COMMAND_DESCRIPTIONS.get(name, ""))])
        positional = [
            action
            for action in subparser._actions
            if not action.option_strings and action.dest not in {"help"}
        ]
        if positional:
            lines.append(".SS POSITIONAL ARGUMENTS")
            for action in positional:
                lines.extend([".TP", f"\\fB{_roff(action.dest)}\\fR", _roff(action.help or "")])
        options = _iter_options(subparser)
        if options:
            lines.append(".SS OPTIONS")
            for option, description in options:
                lines.extend([".TP", f"\\fB{_roff(option)}\\fR", _roff(description)])

    lines.extend([".SH EXAMPLES", ".nf"])
    lines.extend(_roff(example) for example in EXAMPLES)
    lines.extend(
        [
            ".fi",
            ".SH FILES",
            _roff("Linux config: ~/.config/eodinga/config.toml"),
            ".br",
            _roff("Linux index: ~/.local/share/eodinga/index.db"),
            ".br",
            _roff("Windows config: %APPDATA%\\eodinga\\config.toml"),
            ".br",
            _roff("Windows index: %LOCALAPPDATA%\\eodinga\\index.db"),
            ".SH SEE ALSO",
            _roff("README.md, docs/DSL.md, docs/ACCEPTANCE.md, docs/RELEASE.md"),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    target = Path(__file__).resolve().parents[1] / "docs" / "eodinga.1"
    target.write_text(render_man_page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
