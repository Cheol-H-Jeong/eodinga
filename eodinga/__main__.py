from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from eodinga import __version__
from eodinga.common import SearchResult, StatsSnapshot
from eodinga.config import AppConfig, load
from eodinga.doctor import run_diagnostics
from eodinga.index.storage import open_index
from eodinga.observability import configure_logging
from eodinga.query import QuerySyntaxError, search as run_search


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eodinga")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--db", type=Path)

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--root", type=Path)
    index_parser.add_argument("--rebuild", action="store_true")
    index_parser.set_defaults(handler=_cmd_index)

    watch_parser = subparsers.add_parser("watch")
    watch_parser.set_defaults(handler=_cmd_watch)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--json", action="store_true")
    search_parser.add_argument("--limit", type=int, default=200)
    search_parser.add_argument("--root", type=Path)
    search_parser.set_defaults(handler=_cmd_search)

    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("--json", action="store_true")
    stats_parser.set_defaults(handler=_cmd_stats)

    gui_parser = subparsers.add_parser("gui")
    gui_parser.add_argument("--test-mode", action="store_true")
    gui_parser.set_defaults(handler=_cmd_gui)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.set_defaults(handler=_cmd_doctor)

    version_parser = subparsers.add_parser("version")
    version_parser.set_defaults(handler=_cmd_version)
    return parser


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported JSON type: {type(value)!r}")


def _emit(payload: Any, as_json: bool = False) -> int:
    if as_json:
        sys.stdout.write(json.dumps(payload, default=_json_default))
        sys.stdout.write("\n")
        return 0
    sys.stdout.write(f"{payload}\n")
    return 0


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    return load(args.config)


def _normalize_search_root(root: Path | None) -> Path | None:
    if root is None:
        return None
    root_text = str(root)
    if re.match(r"^[A-Za-z]:[\\/]", root_text) or root_text.startswith("\\\\"):
        return Path(root_text)
    return root.resolve()


def _cmd_index(args: argparse.Namespace) -> int:
    payload = {
        "command": "index",
        "root": str(args.root) if args.root else None,
        "rebuild": bool(args.rebuild),
        "db": str(args.db) if args.db else None,
    }
    return _emit(payload, as_json=True)


def _cmd_watch(args: argparse.Namespace) -> int:
    payload = {"command": "watch", "db": str(args.db) if args.db else None}
    return _emit(payload, as_json=True)


def _cmd_search(args: argparse.Namespace) -> int:
    _resolve_config(args)
    limit = max(int(args.limit), 0)
    root = _normalize_search_root(args.root)
    try:
        with closing(open_index(args.db or _resolve_config(args).index.db_path)) as conn:
            query_result = run_search(conn, args.query, limit=limit, root=root)
    except (QuerySyntaxError, ValueError) as error:
        sys.stderr.write(f"{error}\n")
        return 2

    hits = query_result.hits
    results = [
        SearchResult(
            path=hit.file.path,
            score=hit.match_score,
            snippet=hit.snippet,
        ).model_dump(mode="json")
        for hit in hits[:limit]
    ]
    payload = {
        "query": args.query,
        "results": results,
        "count": query_result.total_estimate,
        "returned": len(results),
        "elapsed_ms": query_result.elapsed_ms,
    }
    return _emit(payload, as_json=bool(args.json))


def _cmd_stats(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    snapshot = StatsSnapshot(
        files_indexed=0,
        documents_indexed=0,
        roots=[root.path for root in config.roots],
        db_path=args.db or config.index.db_path,
    ).model_dump(mode="json")
    return _emit(snapshot, as_json=bool(args.json))


def _cmd_gui(args: argparse.Namespace) -> int:
    from eodinga.gui.app import launch_gui

    test_mode = bool(args.test_mode) or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    config = _resolve_config(args)
    db_path = args.db or config.index.db_path
    if test_mode:
        launched = launch_gui(test_mode=True, db_path=db_path)
        app, window, launcher = launched
        launcher.close()
        window.close()
        app.processEvents()
        return 0
    return int(launch_gui(test_mode=False, db_path=db_path))


def _cmd_doctor(args: argparse.Namespace) -> int:
    config = _resolve_config(args)
    report, exit_code = run_diagnostics(config=config, db_path=args.db)
    _emit(report, as_json=True)
    return exit_code


def _cmd_version(args: argparse.Namespace) -> int:
    return _emit(__version__)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
