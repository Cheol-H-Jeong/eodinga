from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.gui.app import EodingaWindow
from eodinga.gui.launcher_window import LauncherWindow
from eodinga.gui.theme import apply_theme


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _demo_search(query: str, limit: int) -> QueryResult:
    items = [
        SearchHit(
            path=Path("/workspace/projects/specs/v0.1-checklist.md"),
            parent_path=Path("/workspace/projects/specs"),
            name="v0.1-checklist.md",
            highlighted_name="v0.1-checklist.md",
            highlighted_path="/workspace/projects/specs/v0.1-checklist.md",
        ),
        SearchHit(
            path=Path("/workspace/projects/design/release-notes.pdf"),
            parent_path=Path("/workspace/projects/design"),
            name="release-notes.pdf",
            highlighted_name="release-notes.pdf",
            highlighted_path="/workspace/projects/design/release-notes.pdf",
        ),
        SearchHit(
            path=Path("/workspace/문서/회의록-봄.txt"),
            parent_path=Path("/workspace/문서"),
            name="회의록-봄.txt",
            highlighted_name="회의록-봄.txt",
            highlighted_path="/workspace/문서/회의록-봄.txt",
        ),
    ]
    if not query:
        return QueryResult(items=[], total=0, elapsed_ms=1.4)
    return QueryResult(items=items[:limit], total=len(items), elapsed_ms=7.8)


def render_doc_screenshots(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = cast(QApplication, QApplication.instance() or QApplication([]))
    apply_theme(app, "light")

    window = EodingaWindow(search_fn=_demo_search)
    launcher = LauncherWindow(search_fn=_demo_search)

    try:
        indexing_status = IndexingStatus(
            phase="indexing",
            processed_files=1248,
            total_files=3200,
            current_root=Path("/workspace/projects"),
        )
        window.set_indexing_status(indexing_status)
        window.tab_widget.setCurrentWidget(window.search_tab)
        window.show()
        launcher.show()
        window.search_tab.launcher_panel.query_field.setText("release")
        window.search_tab.launcher_panel._run_query()
        launcher.query_field.setText("release")
        launcher._run_query()
        _wait(80)

        app.processEvents()

        app_path = output_dir / "app-window.png"
        launcher_path = output_dir / "launcher-window.png"
        index_path = output_dir / "index-progress.png"
        settings_path = output_dir / "settings-window.png"

        if not window.grab().save(str(app_path)):
            raise RuntimeError(f"failed to save screenshot: {app_path}")
        if not launcher.grab().save(str(launcher_path)):
            raise RuntimeError(f"failed to save screenshot: {launcher_path}")

        window.tab_widget.setCurrentWidget(window.index_tab)
        _wait(40)
        app.processEvents()

        if not window.grab().save(str(index_path)):
            raise RuntimeError(f"failed to save screenshot: {index_path}")
        window.tab_widget.setCurrentWidget(window.settings_tab)
        _wait(40)
        app.processEvents()

        if not window.grab().save(str(settings_path)):
            raise RuntimeError(f"failed to save screenshot: {settings_path}")
        return {
            "app-window": app_path,
            "launcher-window": launcher_path,
            "index-progress": index_path,
            "settings-window": settings_path,
        }
    finally:
        launcher.close()
        window.close()
        app.processEvents()


__all__ = ["render_doc_screenshots"]
