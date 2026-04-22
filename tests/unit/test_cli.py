from __future__ import annotations

import json

from eodinga import __version__


def test_all_subcommands_help_succeed(cli_runner) -> None:
    for command in ("index", "watch", "search", "stats", "gui", "doctor", "version"):
        result = cli_runner(command, "--help")
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()


def test_search_json_returns_json(cli_runner) -> None:
    result = cli_runner("search", "needle", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "needle"
    assert isinstance(payload["results"], list)


def test_version_matches_package(cli_runner) -> None:
    result = cli_runner("version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_gui_smoke_succeeds_offscreen(cli_runner) -> None:
    result = cli_runner("gui")
    assert result.returncode == 0
