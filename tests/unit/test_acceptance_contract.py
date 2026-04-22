from __future__ import annotations

import re


def test_top_level_help_lists_spec_subcommands(cli_runner) -> None:
    result = cli_runner("--help")

    assert result.returncode == 0

    match = re.search(r"\{([^}]+)\}", result.stdout)
    assert match is not None
    subcommands = [item.strip() for item in match.group(1).split(",")]

    assert subcommands == [
        "index",
        "watch",
        "search",
        "stats",
        "gui",
        "doctor",
        "version",
    ]

