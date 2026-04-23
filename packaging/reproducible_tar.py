from __future__ import annotations

import argparse
import gzip
import os
import tarfile
from pathlib import Path


def _normalized_mode(path: Path) -> int:
    if path.is_dir():
        return 0o755
    if os.access(path, os.X_OK):
        return 0o755
    return 0o644


def _iter_paths(root: Path) -> list[Path]:
    return [root, *sorted(path for path in root.rglob("*"))]


def build_archive(source_dir: Path, output_path: Path) -> None:
    source_dir = source_dir.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in _iter_paths(source_dir):
                    arcname = source_dir.name if path == source_dir else str(Path(source_dir.name) / path.relative_to(source_dir))
                    info = archive.gettarinfo(str(path), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mtime = 0
                    info.mode = _normalized_mode(path)
                    if info.isfile():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_archive(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
