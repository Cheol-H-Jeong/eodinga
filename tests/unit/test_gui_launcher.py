from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer

from eodinga.common import QueryResult, SearchHit
from eodinga.gui.launcher import LauncherWindow


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_launcher_debounces_and_updates_results(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path(f"/tmp/{query}.txt"),
                    parent_path=Path("/tmp"),
                    name=f"{query}.txt",
                    highlighted_name=f"<mark>{query}</mark>.txt",
                    highlighted_path=f"/tmp/<mark>{query}</mark>.txt",
                )
            ],
            total=1,
            elapsed_ms=9.5,
        )

    launcher = LauncherWindow(search_fn=search_fn)
    launcher.show()

    launcher.query_field.setText("report")
    _wait(60)

    assert launcher.model.rowCount() == 1
    assert launcher.status_label.text() == "1 results · 9.5 ms"
    result = launcher.model.item_at(0)
    assert result is not None
    assert result.name == "report.txt"

