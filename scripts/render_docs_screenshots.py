from __future__ import annotations

import os
from pathlib import Path

from eodinga.gui.docs import render_doc_screenshots


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
    render_doc_screenshots(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
