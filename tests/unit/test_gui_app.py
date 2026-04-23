from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QSystemTrayIcon

from eodinga.common import IndexingStatus, QueryResult, SearchHit
from eodinga.config import AppConfig, load
from eodinga.gui.actions import DesktopActions
from eodinga.gui.app import EodingaWindow, build_index_search_fn, launch_gui
from eodinga.gui.launcher_window import LauncherWindow
from eodinga.gui.tabs import AboutTab, IndexTab, RootsTab, SearchTab, SettingsTab
from eodinga.index.schema import apply_schema


class _HotkeyServiceSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.callback = None

    def register(self, combo: str, callback) -> None:
        self.calls.append(("register", combo))
        self.callback = callback

    def unregister(self) -> None:
        self.calls.append(("unregister", ""))
        self.callback = None

    def start(self) -> None:
        self.calls.append(("start", ""))

    def stop(self) -> None:
        self.calls.append(("stop", ""))


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


def test_app_accessible_names_cover_main_interactive_widgets(qapp) -> None:
    window = EodingaWindow()
    window.show()

    assert window.tab_widget.accessibleName() == "Main navigation tabs"
    assert window.roots_tab.accessibleName() == "Roots tab"
    assert window.roots_tab.add_root_button.accessibleName() == "Add root"
    assert window.roots_tab.remove_root_button.accessibleName() == "Remove selected root"
    assert window.index_tab.accessibleName() == "Index tab"
    assert window.index_tab.rebuild_button.accessibleName() == "Rebuild index"
    assert window.search_tab.accessibleName() == "Search tab"
    assert window.settings_tab.accessibleName() == "Settings tab"
    assert window.settings_tab.system_theme_checkbox.accessibleName() == "Use system theme"
    assert window.settings_tab.frameless_checkbox.accessibleName() == "Use frameless launcher window"
    assert window.settings_tab.always_on_top_checkbox.accessibleName() == "Keep launcher always on top"
    assert window.settings_tab.hotkey_label.accessibleName() == "Current launcher hotkey"
    assert window.settings_tab.remap_hotkey_button.accessibleName() == "Remap hotkey"
    assert window.about_tab.accessibleName() == "About tab"
    assert window.launcher_window.pinned_queries_row.accessibleName() == "Pinned launcher queries"
    assert window.launcher_window.recent_queries_row.accessibleName() == "Recent launcher queries"
    assert window.launcher_window.empty_state.accessibleName() == "Launcher empty state"
    assert window.launcher_window.preview_pane.accessibleName() == "Launcher preview pane"
    assert window.search_tab.launcher_panel.action_bar.accessibleName() == "Launcher action bar"
    assert window.search_tab.launcher_panel.status_chip.accessibleName() == "Status"


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


def test_launchers_respect_configured_limit_and_debounce(qapp) -> None:
    calls: list[tuple[str, int]] = []

    def search_fn(query: str, limit: int) -> QueryResult:
        calls.append((query, limit))
        return QueryResult(items=[], total=0, elapsed_ms=1.0)

    config = AppConfig()
    config.launcher = config.launcher.model_copy(update={"max_results": 7, "debounce_ms": 90})
    window = EodingaWindow(search_fn=search_fn, config=config)

    assert window.launcher_window._debounce_timer.interval() == 90
    assert window.search_tab.launcher_panel._debounce_timer.interval() == 90

    window.launcher_window.query_field.setText("popup")
    window.search_tab.launcher_panel.query_field.setText("embedded")
    QTest.qWait(40)
    assert calls == []

    QTest.qWait(80)
    assert calls == [("popup", 7), ("embedded", 7)]


def test_tray_indicator_can_show_launcher_without_tray_backend(qapp) -> None:
    window = EodingaWindow()

    assert not window.launcher_window.isVisible()

    window.tray_indicator.show_launcher()

    assert window.launcher_window.isVisible()


def test_tray_indicator_exposes_open_window_and_toggle_launcher_actions(qapp) -> None:
    window = EodingaWindow()
    window.hide()

    assert window.tray_indicator.open_app_action.text() == "Open eodinga"
    assert window.tray_indicator.toggle_launcher_action.text() == "Show launcher"

    window.tray_indicator.show_main_window()
    qapp.processEvents()
    assert window.isVisible()

    window.tray_indicator.toggle_launcher()
    qapp.processEvents()
    assert window.launcher_window.isVisible()
    assert window.tray_indicator.toggle_launcher_action.text() == "Hide launcher"

    window.tray_indicator.toggle_launcher()
    qapp.processEvents()
    assert not window.launcher_window.isVisible()
    assert window.tray_indicator.toggle_launcher_action.text() == "Show launcher"


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
    assert restored_launcher.pos().x() >= 0
    assert restored_launcher.pos().y() >= 0

    restored_window.close()
    qapp.processEvents()


def test_launcher_restore_clamps_geometry_to_available_screen(qapp, monkeypatch, temp_config_path: Path) -> None:
    config = AppConfig()
    config.launcher = config.launcher.model_copy(
        update={
            "window_x": 5000,
            "window_y": -320,
            "window_width": 1600,
            "window_height": 1200,
        }
    )
    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )
    monkeypatch.setattr(launcher, "_available_geometry", lambda: QRect(20, 40, 800, 600))

    launcher.show()
    qapp.processEvents()

    geometry = launcher.geometry()
    assert geometry.x() == 20
    assert geometry.y() == 40
    assert geometry.width() == 800
    assert geometry.height() == 600

    launcher.hide()
    qapp.processEvents()

    stored = load(temp_config_path)
    assert stored.launcher.window_x == 20
    assert stored.launcher.window_y == 40
    assert stored.launcher.window_width == 800
    assert stored.launcher.window_height == 600

    window.close()
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


def test_launcher_respects_frameless_config(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    config.launcher = config.launcher.model_copy(update={"frameless": False})
    _, window, launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )

    assert not bool(launcher.windowFlags() & Qt.WindowType.FramelessWindowHint)

    window.close()
    qapp.processEvents()

    config.launcher = config.launcher.model_copy(update={"frameless": True})
    _, framed_window, framed_launcher = cast(
        tuple[object, EodingaWindow, LauncherWindow],
        launch_gui(test_mode=True, config=config, config_path=temp_config_path),
    )

    assert bool(framed_launcher.windowFlags() & Qt.WindowType.FramelessWindowHint)

    framed_window.close()
    qapp.processEvents()


def test_tray_activation_toggles_launcher_visibility(qapp) -> None:
    window = EodingaWindow()

    window.tray_indicator._handle_activation(QSystemTrayIcon.ActivationReason.Trigger)
    qapp.processEvents()
    assert window.launcher_window.isVisible()

    window.tray_indicator._handle_activation(QSystemTrayIcon.ActivationReason.Trigger)
    qapp.processEvents()
    assert not window.launcher_window.isVisible()


def test_tray_quit_action_calls_application_quit(monkeypatch, qapp) -> None:
    called: list[str] = []
    monkeypatch.setattr("eodinga.gui.app.QSystemTrayIcon.isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(qapp, "quit", lambda: called.append("quit"))

    window = EodingaWindow()

    window.tray_indicator.quit_action.trigger()

    assert called == ["quit"]


def test_window_registers_hotkey_and_toggles_launcher_from_callback(qapp) -> None:
    hotkey_service = _HotkeyServiceSpy()
    config = AppConfig()
    window = EodingaWindow(config=config, hotkey_service=hotkey_service)

    assert hotkey_service.calls == [
        ("stop", ""),
        ("unregister", ""),
        ("register", "ctrl+shift+space"),
        ("start", ""),
    ]
    assert hotkey_service.callback is not None
    assert not window.launcher_window.isVisible()

    hotkey_service.callback()
    qapp.processEvents()
    assert window.launcher_window.isVisible()

    hotkey_service.callback()
    qapp.processEvents()
    assert not window.launcher_window.isVisible()

    window.close()
    qapp.processEvents()
    assert hotkey_service.calls[-1] == ("stop", "")


def test_settings_tab_rebinds_hotkey_without_restart(
    monkeypatch,
    qapp,
    temp_config_path: Path,
) -> None:
    hotkey_service = _HotkeyServiceSpy()
    config = AppConfig()
    window = EodingaWindow(config=config, config_path=temp_config_path, hotkey_service=hotkey_service)
    monkeypatch.setattr(
        "eodinga.gui.tabs.settings.QInputDialog.getText",
        lambda *args, **kwargs: ("ctrl+alt+k", True),
    )

    window.settings_tab.remap_hotkey_button.click()
    qapp.processEvents()

    assert hotkey_service.calls[-4:] == [
        ("stop", ""),
        ("unregister", ""),
        ("register", "ctrl+alt+k"),
        ("start", ""),
    ]
    assert window.settings_tab.hotkey_label.text() == "Launcher hotkey: ctrl+alt+k"
    assert load(temp_config_path).launcher.hotkey == "ctrl+alt+k"


def test_settings_tab_toggles_always_on_top_without_restart(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    config.launcher = config.launcher.model_copy(update={"always_on_top": False})
    window = EodingaWindow(config=config, config_path=temp_config_path)
    window.launcher_window.show()
    qapp.processEvents()

    window.settings_tab.always_on_top_checkbox.click()
    qapp.processEvents()

    assert bool(window.launcher_window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert load(temp_config_path).launcher.always_on_top is True


def test_settings_tab_toggles_frameless_without_restart(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    config.launcher = config.launcher.model_copy(update={"frameless": True})
    window = EodingaWindow(config=config, config_path=temp_config_path)
    window.launcher_window.show()
    qapp.processEvents()

    window.settings_tab.frameless_checkbox.click()
    qapp.processEvents()

    assert not bool(window.launcher_window.windowFlags() & Qt.WindowType.FramelessWindowHint)
    assert load(temp_config_path).launcher.frameless is False


def test_launcher_flag_toggles_preserve_geometry(qapp, temp_config_path: Path) -> None:
    config = AppConfig()
    window = EodingaWindow(config=config, config_path=temp_config_path)
    launcher = window.launcher_window
    launcher.show()
    launcher.move(210, 120)
    launcher.resize(760, 540)
    qapp.processEvents()

    before = launcher.geometry()

    launcher.set_always_on_top(True)
    qapp.processEvents()
    assert launcher.geometry() == before

    launcher.set_frameless(False)
    qapp.processEvents()
    assert launcher.geometry() == before


class _ActionSpy:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.revealed: list[str] = []
        self.properties: list[str] = []
        self.copied: list[str] = []
        self.copied_names: list[str] = []

    def open_hit(self, hit: SearchHit) -> None:
        self.opened.append(hit.name)

    def reveal_hit(self, hit: SearchHit) -> None:
        self.revealed.append(hit.name)

    def show_properties(self, hit: SearchHit) -> None:
        self.properties.append(hit.name)

    def copy_hit_path(self, hit: SearchHit) -> None:
        self.copied.append(str(hit.path))

    def copy_hit_name(self, hit: SearchHit) -> None:
        self.copied_names.append(hit.name)


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

    for index, launcher in enumerate((window.launcher_window, window.search_tab.launcher_panel)):
        launcher.query_field.setText("release")
        launcher._run_query()
        launcher.activate_current_result()
        launcher.emit_open_containing_folder()
        launcher.emit_show_properties()
        launcher.emit_copy_path()
        launcher.emit_copy_name()

    assert spy.opened == ["release-notes.txt", "release-notes.txt"]
    assert spy.revealed == ["release-notes.txt", "release-notes.txt"]
    assert spy.properties == ["release-notes.txt", "release-notes.txt"]
    assert spy.copied == ["/tmp/release-notes.txt", "/tmp/release-notes.txt"]
    assert spy.copied_names == ["release-notes.txt", "release-notes.txt"]


def test_desktop_actions_copy_path_updates_clipboard(qapp) -> None:
    actions = DesktopActions(qapp)
    hit = SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")

    actions.copy_hit_path(hit)

    assert qapp.clipboard().text() == "/tmp/report.txt"


def test_desktop_actions_copy_name_updates_clipboard(qapp) -> None:
    actions = DesktopActions(qapp)
    hit = SearchHit(path=Path("/tmp/report.txt"), parent_path=Path("/tmp"), name="report.txt")

    actions.copy_hit_name(hit)

    assert qapp.clipboard().text() == "report.txt"


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
