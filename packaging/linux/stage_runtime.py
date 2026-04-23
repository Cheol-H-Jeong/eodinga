from __future__ import annotations

import shutil
import sys
import tomllib
from pathlib import Path


def declared_package_data_paths(project_root: Path) -> list[str]:
    payload = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = payload.get("tool", {}).get("setuptools", {}).get("package-data", {})
    declared: set[str] = set()
    for package_name, patterns in package_data.items():
        package_root = project_root.joinpath(*package_name.split("."))
        for pattern in patterns:
            for matched_path in package_root.glob(pattern):
                if matched_path.is_file():
                    declared.add(matched_path.relative_to(project_root).as_posix())
    return sorted(declared)


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
