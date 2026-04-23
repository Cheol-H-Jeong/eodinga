from __future__ import annotations

from pathlib import Path

from eodinga.__main__ import _build_parser


def _usage_block(parser) -> str:
    return parser.format_usage().replace("usage: ", "").strip()


def build_man_page() -> str:
    parser = _build_parser()
    sections: list[str] = [
        ".TH EODINGA 1",
        ".SH NAME",
        "eodinga \\- everything-class instant file search for Windows and Linux",
        ".SH SYNOPSIS",
        f"\\fBeodinga\\fR {_usage_block(parser)}",
        ".SH DESCRIPTION",
        (
            "eodinga indexes local filesystem metadata and optional document text, "
            "keeps the index fresh through filesystem notifications, and exposes "
            "the same lexical query engine through CLI, GUI, and launcher surfaces."
        ),
        ".SH GLOBAL OPTIONS",
        ".TP",
        "\\fB--log-level\\fR LEVEL",
        "Set the runtime log level. Defaults to INFO.",
        ".TP",
        "\\fB--config\\fR PATH",
        "Load configuration from PATH instead of the platform default.",
        ".TP",
        "\\fB--db\\fR PATH",
        "Open the SQLite index at PATH instead of the configured default.",
        ".SH COMMANDS",
    ]

    for name in ("index", "watch", "search", "stats", "gui", "doctor", "version"):
        subparser = parser._subparsers._group_actions[0].choices[name]
        sections.extend(
            [
                ".TP",
                f"\\fBeodinga {name}\\fR",
                _usage_block(subparser),
            ]
        )
    sections.extend(
        [
            ".SH EXAMPLES",
            ".TP",
            "\\fBeodinga index --root ~/projects --root ~/docs\\fR",
            "Build or rebuild the local index for two roots.",
            ".TP",
            "\\fBeodinga search 'ext:pdf content:\"release checklist\"' --limit 20\\fR",
            "Run a lexical search with path/content filters and a result limit.",
            ".TP",
            "\\fBeodinga stats --json\\fR",
            "Emit index counts plus in-process observability counters as JSON.",
            ".TP",
            "\\fBeodinga doctor\\fR",
            "Run the local diagnostics surface for config, dependencies, and index state.",
            ".SH FILES",
            "\\fI~/.config/eodinga/config.toml\\fR on Linux or \\fI%APPDATA%\\\\eodinga\\\\config.toml\\fR on Windows.",
            ".br",
            "\\fI~/.local/share/eodinga/index.db\\fR on Linux or \\fI%LOCALAPPDATA%\\\\eodinga\\\\index.db\\fR on Windows.",
            ".SH SEE ALSO",
            "\\fIREADME.md\\fR, \\fIdocs/DSL.md\\fR, \\fIdocs/ARCHITECTURE.md\\fR, \\fIdocs/RELEASE.md\\fR",
        ]
    )
    return "\n".join(sections) + "\n"


def main() -> int:
    target = Path(__file__).resolve().parents[1] / "docs" / "eodinga.1"
    target.write_text(build_man_page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
