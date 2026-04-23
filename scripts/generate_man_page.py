from __future__ import annotations

import argparse
from pathlib import Path

from eodinga import __version__
from eodinga.__main__ import _build_parser


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "eodinga.1"


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("-", r"\-")


def _section(title: str) -> str:
    return f".SH {_escape(title.upper())}"


def _subsection(title: str) -> str:
    return f".SS {_escape(title)}"


def _literal_block(text: str) -> list[str]:
    return [".nf", *(_escape(line.rstrip()) for line in text.strip("\n").splitlines()), ".fi"]


def _iter_option_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        action
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction) and action.dest != "help"
    ]


def _find_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise RuntimeError("expected subparsers in eodinga CLI parser")


def _action_label(action: argparse.Action) -> str:
    if action.option_strings:
        label = ", ".join(action.option_strings)
        if action.metavar:
            label = f"{label} {action.metavar}"
        elif action.nargs != 0 and action.dest not in {"json", "rebuild", "test_mode"}:
            label = f"{label} {action.dest.upper()}"
        return label
    return action.metavar or action.dest.upper()


def _action_help(action: argparse.Action) -> str:
    help_text = action.help if action.help not in {None, argparse.SUPPRESS} else ""
    if help_text:
        return help_text
    if action.option_strings:
        return "argparse option exported from the shipped CLI surface."
    return "argparse positional argument exported from the shipped CLI surface."


def build_man_page() -> str:
    parser = _build_parser()
    subparsers = _find_subparsers(parser)

    lines = [
        f'.TH EODINGA 1 "2026-04-23" "eodinga {__version__}" "User Commands"',
        _section("Name"),
        r"eodinga \- local-first lexical file search for Windows and Linux",
        _section("Synopsis"),
        ".B eodinga",
        "[\\-h] [\\-\\-log\\-level LOG_LEVEL] [\\-\\-config CONFIG] [\\-\\-db DB]",
        r"\fICOMMAND\fR ...",
        _section("Description"),
        (
            "Indexes filenames, paths, and optional parsed document text into a local SQLite/FTS5 "
            "database, then exposes the same search engine through CLI, GUI, and launcher surfaces."
        ),
        _section("Global Options"),
    ]

    for action in _iter_option_actions(parser):
        lines.extend(
            [
                ".TP",
                rf"\fB{_escape(_action_label(action))}\fR",
                _escape(_action_help(action)),
            ]
        )

    lines.extend([_section("Commands")])
    for name, command in subparsers.choices.items():
        summary = (command.description or command.format_usage()).replace("\n", " ").strip()
        lines.extend(
            [
                ".TP",
                rf"\fB{_escape(name)}\fR",
                _escape(summary),
            ]
        )

    lines.extend([_section("Command Reference")])
    for name, command in subparsers.choices.items():
        lines.append(_subsection(name))
        lines.extend(_literal_block(command.format_usage()))
        command_actions = _iter_option_actions(command)
        if command_actions:
            for action in command_actions:
                lines.extend(
                    [
                        ".TP",
                        rf"\fB{_escape(_action_label(action))}\fR",
                        _escape(_action_help(action)),
                    ]
                )

    lines.extend(
        [
            _section("Examples"),
            ".TP",
            r"\fBeodinga index \-\-root ~/projects \-\-root ~/docs\fR",
            "Build or rebuild a local index from multiple roots.",
            ".TP",
            "\\fBeodinga search 'ext:pdf content:\\\"release checklist\\\"' \\-\\-limit 20\\fR",
            "Run a structured search and emit text output.",
            ".TP",
            r"\fBeodinga stats \-\-json\fR",
            "Inspect the active database path, roots, and runtime counters in JSON form.",
            ".TP",
            r"\fBeodinga gui\fR",
            "Launch the Qt shell and launcher integration surface.",
            _section("Files"),
            "~/.config/eodinga/config.toml on Linux or %APPDATA%\\eodinga\\config.toml on Windows stores configuration.",
            "~/.local/share/eodinga/index.db on Linux or %LOCALAPPDATA%\\eodinga\\index.db on Windows stores the local index.",
            _section("Maintenance"),
            "Regenerate this page with python scripts/generate_man_page.py after argparse-visible CLI changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    OUTPUT_PATH.write_text(build_man_page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
