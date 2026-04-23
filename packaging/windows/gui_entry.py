from __future__ import annotations

import sys

from eodinga.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main(["gui", *sys.argv[1:]]))
