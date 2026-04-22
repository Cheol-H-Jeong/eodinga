from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSystemTrayIcon

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.config import AppConfig, load
from eodinga.gui.actions import DesktopActions
from eodinga.gui.app import EodingaWindow, build_index_search_fn, launch_gui
from eodinga.gui.launcher import LauncherWindow
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab
from eodinga.index.schema import apply_schema


def test_app_window_has_expected_tabs_and_launcher(qapp) -> None:
    _, window, launcher = cast(tuple[object, EodingaWindow, LauncherWindow], launch_gui(test_mode=True))
    window.show()

    assert window.tab_widget.count() == 5
    assert isinstance(window.roots_tab, RootsTab)
    assert isinstance(window.index_tab, IndexTab)
    assert isinstance(window.search_tab, SearchTab)
    assert isinstance(window.settings_tab, SettingsTab)
    assert isinstance(window.about_tab, AboutTab)
    assert launcher is window.launcher_window
    assert window.launcher_window.parent() is None


def test_app_updates_index_status_in_tab_and_tray(qapp) -> None:
    window = EodingaWindow()
    status = IndexingStatus(phase="indexing", processed_files=12, total_files=40, current_root=Path("/tmp/docs"))

    window.set_indexing_status(status)

    assert window.index_tab.status_chip.text() == "Indexing"
    assert "12/40 files indexed" in window.index_tab.progress_label.text()
    assert "/tmp/docs" in window.tray_indicator.tooltip
    assert "(30%)" in window.tray_indicator.status_text
    assert window.tray_indicator.icon_state == "indexing"

    window.set_indexing_status(IndexingStatus())

    assert window.tray_indicator.icon_state == "idle"


def test_launcher_state_is_shared_between_popup_and_search_tab(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[SearchHit(path=Path("/tmp/release-notes.txt"), parent_path=Path("/tmp"), name="release-notes.txt")][
                :limit
            ],
            total=1,
            elapsed_ms=4.0,
        )

    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, search_fn=search_fn),
    )
    launcher.query_field.setText("release")
    launcher._run_query()

    assert "release" in window.search_tab.launcher_panel.empty_state.body_label.text()


def test_tray_indicator_can_show_launcher_without_tray_backend(qapp) -> None:
    window = EodingaWindow()

    assert not window.launcher_window.isVisible()

    window.tray_indicator.show_launcher()

    assert window.launcher_window.isVisible()


def test_launcher_geometry_persists_to_config_and_restores(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )

    launcher.show()
    launcher.move(180, 96)
    launcher.resize(720, 520)
    qapp.processEvents()
    launcher.hide()
    qapp.processEvents()
    window.close()
    qapp.processEvents()

    stored = load(temp_config_path)
    assert stored.launcher.window_x == 180
    assert stored.launcher.window_y == 96
    assert stored.launcher.window_width == 720
    assert stored.launcher.window_height == 520

    _, restored_window, restored_launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=stored, config_path=temp_config_path),
    )
    restored_launcher.show()
    qapp.processEvents()

    assert restored_launcher.width() == 720
    assert restored_launcher.height() == 520
    assert restored_launcher.pos().x() == 180
    assert restored_launcher.pos().y() == 96

    restored_window.close()
    qapp.processEvents()


def test_launcher_respects_always_on_top_config(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    config.launcher = config.launcher.model_copy(update={"always_on_top": False})
    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )

    assert not bool(launcher.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    window.close()
    qapp.processEvents()

    config.launcher = config.launcher.model_copy(update={"always_on_top": True})
    _, top_window, top_launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )

    assert bool(top_launcher.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    top_window.close()
    qapp.processEvents()


def test_tray_activation_toggles_launcher_visibility(qapp) -> None:
    window = EodingaWindow()

    window.tray_indicator._handle_activation(QSystemTrayIcon.ActivationReason.Trigger)
    qapp.processEvents()
    assert window.launcher_window.isVisible()

    window.tray_indicator._handle_activation(QSystemTrayIcon.ActivationReason.Trigger)
    qapp.processEvents()
    assert not window.launcher_window.isVisible()


class _ActionSpy:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.revealed: list[str] = []
        self.properties: list[str] = []
        self.copied: list[str] = []

    def open_hit(self, hit: SearchHit) -> None:
        self.opened.append(hit.name)

    def reveal_hit(self, hit: SearchHit) -> None:
        self.revealed.append(hit.name)

    def show_properties(self, hit: SearchHit) -> None:
        self.properties.append(hit.name)

    def copy_hit_path(self, hit: SearchHit) -> None:
        self.copied.append(str(hit.path))


def test_app_wires_launcher_shortcuts_to_desktop_actions(qapp) -> None:
    def search_fn(query: str, limit: int) -> QueryResult:
        return QueryResult(
            items=[
                SearchHit(
                    path=Path("/tmp/release-notes.txt"),
                    parent_path=Path("/tmp"),
                    name="release-notes.txt",
                )
            ][:limit],
            total=1,
            elapsed_ms=2.0,
        )

    spy = _ActionSpy()
    window = EodingaWindow(search_fn=search_fn, desktop_actions=spy)

    for launcher in (window.launcher_window, window.search_tab.launcher_panel):
        launcher.query_field.setText("release")
        launcher._run_query()
        launcher.activate_current_result()
        launcher.emit_open_containing_folder()
        launcher.emit_show_properties()
        launcher.emit_copy_path()

    assert spy.opened == ["release-notes.txt", "release-notes.txt"]
    assert spy.revealed == ["release-notes.txt", "release-notes.txt"]
    assert spy.properties == ["release-notes.txt", "release-notes.txt"]
    assert spy.copied == ["/tmp/release-notes.txt", "/tmp/release-notes.txt"]


def test_desktop_actions_copy_path_updates_clipboard(qapp) -> None:
    actions = DesktopActions(qapp)
    hit = SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")

    actions.copy_hit_path(hit)

    assert qapp.clipboard().text() == "/tmp/report.txt"


def test_build_index_search_fn_queries_real_index(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO roots(id, path, include, exclude, added_at) VALUES (?, ?, ?, ?, ?)",
            (1, str(tmp_path), "[]", "[]", 1),
        )
        target_path = tmp_path / "docs" / "release-notes.txt"
        conn.execute(
            """
            INSERT INTO files (
              id, root_id, path, parent_path, name, name_lower, ext, size, mtime, ctime,
              is_dir, is_symlink, content_hash, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                str(target_path),
                str(target_path.parent),
                target_path.name,
                target_path.name.lower(),
                "txt",
                1024,
                1,
                1,
                0,
                0,
                b"release",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO content_fts(rowid, title, head_text, body_text) VALUES (?, ?, ?, ?)",
            (1, target_path.name, "release notes", "release notes are attached"),
        )
        conn.execute(
            """
            INSERT INTO content_map(file_id, fts_rowid, parser, parsed_at, content_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (1, 1, "text", 1, b"release"),
        )
        conn.commit()
    finally:
        conn.close()

    search_fn = build_index_search_fn(db_path)
    result = search_fn('content:"release notes"', 5)

    assert result.total == 1
    assert result.items[0].name == "release-notes.txt"
    assert result.items[0].snippet is not None


def test_build_index_search_fn_returns_empty_results_for_invalid_query(tmp_path: Path) -> None:
    search_fn = build_index_search_fn(tmp_path / "index.db")

    result = search_fn('content:"unterminated', 5)

    assert result.total == 0
    assert result.items == []
