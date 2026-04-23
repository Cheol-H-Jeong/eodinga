from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: stage_runtime.py <runtime-root>", file=sys.stderr)
        return 2

    runtime_root = Path(args[0]).resolve()
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / "eodinga"
    target = runtime_root / "eodinga"

    runtime_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
