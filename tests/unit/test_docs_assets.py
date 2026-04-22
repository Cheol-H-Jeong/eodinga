from __future__ import annotations

from pathlib import Path

from eodinga.gui.docs import render_doc_screenshots


def test_render_doc_screenshots_writes_expected_assets(tmp_path: Path, qapp) -> None:
    app_path, launcher_path = render_doc_screenshots(tmp_path)

    assert app_path.name == "app-window.png"
    assert launcher_path.name == "launcher-window.png"
    assert app_path.exists()
    assert launcher_path.exists()
    assert app_path.stat().st_size > 0
    assert launcher_path.stat().st_size > 0
