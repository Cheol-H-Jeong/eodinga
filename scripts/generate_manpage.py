from __future__ import annotations

from argparse import _HelpAction, _SubParsersAction
from pathlib import Path

from eodinga import __version__
from eodinga.__main__ import _build_parser


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


def _option_lines(parser) -> list[str]:
    lines: list[str] = []
    for action in _iter_visible_actions(parser):
        names = action.option_strings or [action.dest]
        heading = ", ".join(names)
        if action.metavar:
            heading = f"{heading} {action.metavar}"
        elif action.option_strings and action.nargs != 0:
            heading = f"{heading} {action.dest.upper()}"
        lines.append(".TP")
        lines.append(rf"\fB{_roff(heading)}\fR")
        lines.append(_roff(action.help or ""))
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
        command_options = _option_lines(command_parser)
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
            r"\fBeodinga search 'date:this-week ext:md roadmap' --limit 20\fR",
            _roff("Run a CLI search using the shared query DSL."),
            ".TP",
            r"\fBeodinga stats --json\fR",
            _roff("Print the active index snapshot and in-memory counters as JSON."),
            ".TP",
            r"\fBeodinga doctor\fR",
            _roff("Check dependencies, writable paths, roots, and hotkey support."),
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
