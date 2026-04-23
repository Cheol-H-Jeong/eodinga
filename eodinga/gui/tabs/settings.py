from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QInputDialog, QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import SecondaryButton


class SettingsTab(QWidget):
    hotkey_change_requested = Signal(str)
    frameless_changed = Signal(bool)
    always_on_top_changed = Signal(bool)
    pinned_queries_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Settings tab")
        self._hotkey_combo = "ctrl+shift+space"
        layout = QVBoxLayout(self)
        title = QLabel("Settings", self)
        title.setProperty("role", "title")
        body = QLabel("Configure the hotkey, theme, and launcher window behavior.", self)
        body.setProperty("role", "secondary")
        self.system_theme_checkbox = QCheckBox("Use system theme", self)
        self.system_theme_checkbox.setAccessibleName("Use system theme")
        self.frameless_checkbox = QCheckBox("Use frameless launcher window", self)
        self.frameless_checkbox.setAccessibleName("Use frameless launcher window")
        self.always_on_top_checkbox = QCheckBox("Keep launcher always on top", self)
        self.always_on_top_checkbox.setAccessibleName("Keep launcher always on top")
        self.hotkey_label = QLabel("", self)
        self.hotkey_label.setProperty("role", "secondary")
        self.hotkey_label.setAccessibleName("Current launcher hotkey")
        self.remap_hotkey_button = SecondaryButton("Remap hotkey", self)
        self.remap_hotkey_button.setAccessibleName("Remap hotkey")
        self.pinned_queries_label = QLabel("", self)
        self.pinned_queries_label.setProperty("role", "secondary")
        self.pinned_queries_label.setWordWrap(True)
        self.pinned_queries_label.setAccessibleName("Pinned launcher queries summary")
        self.manage_pinned_queries_button = SecondaryButton("Manage pinned queries", self)
        self.manage_pinned_queries_button.setAccessibleName("Manage pinned queries")
        self.manage_pinned_queries_button.setAccessibleDescription(
            "Edit the pinned launcher queries shown in the popup and search tab."
        )
        self.clear_pinned_queries_button = SecondaryButton("Clear pinned queries", self)
        self.clear_pinned_queries_button.setAccessibleName("Clear pinned queries")
        self.clear_pinned_queries_button.setAccessibleDescription("Remove all pinned launcher queries.")
        self.remap_hotkey_button.clicked.connect(self._prompt_hotkey_combo)
        self.manage_pinned_queries_button.clicked.connect(self._prompt_pinned_queries)
        self.clear_pinned_queries_button.clicked.connect(lambda: self.pinned_queries_changed.emit([]))
        self.frameless_checkbox.toggled.connect(self.frameless_changed.emit)
        self.always_on_top_checkbox.toggled.connect(self.always_on_top_changed.emit)
        self.set_hotkey_combo(self._hotkey_combo)
        self.set_pinned_queries([])

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.system_theme_checkbox)
        layout.addWidget(self.frameless_checkbox)
        layout.addWidget(self.always_on_top_checkbox)
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.remap_hotkey_button)
        layout.addWidget(self.pinned_queries_label)
        layout.addWidget(self.manage_pinned_queries_button)
        layout.addWidget(self.clear_pinned_queries_button)
        layout.addStretch(1)

    def set_hotkey_combo(self, combo: str) -> None:
        self._hotkey_combo = combo
        self.hotkey_label.setText(f"Launcher hotkey: {combo or 'disabled'}")

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top_checkbox.blockSignals(True)
        self.always_on_top_checkbox.setChecked(enabled)
        self.always_on_top_checkbox.blockSignals(False)

    def set_frameless(self, enabled: bool) -> None:
        self.frameless_checkbox.blockSignals(True)
        self.frameless_checkbox.setChecked(enabled)
        self.frameless_checkbox.blockSignals(False)

    def set_pinned_queries(self, queries: list[str]) -> None:
        normalized = self._normalize_queries(queries)
        if normalized:
            summary = ", ".join(normalized)
            self.pinned_queries_label.setText(f"Pinned queries: {summary}")
            self.pinned_queries_label.setAccessibleDescription(
                f"{len(normalized)} pinned launcher queries: {summary}."
            )
        else:
            self.pinned_queries_label.setText("Pinned queries: none")
            self.pinned_queries_label.setAccessibleDescription("No pinned launcher queries are configured.")
        self.clear_pinned_queries_button.setEnabled(bool(normalized))

    def _prompt_hotkey_combo(self) -> None:
        combo, accepted = QInputDialog.getText(
            self,
            "Remap launcher hotkey",
            "Enter a launcher hotkey:",
            text=self._hotkey_combo,
        )
        if not accepted:
            return
        self.hotkey_change_requested.emit(combo.strip())

    def _prompt_pinned_queries(self) -> None:
        existing = self.pinned_queries_label.text().removeprefix("Pinned queries: ").strip()
        current = "" if existing == "none" else "\n".join(part.strip() for part in existing.split(","))
        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Pinned launcher queries",
            "Enter one launcher query per line:",
            current,
        )
        if not accepted:
            return
        self.pinned_queries_changed.emit(self._normalize_queries(text.splitlines()))

    @staticmethod
    def _normalize_queries(queries: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for query in queries:
            for part in query.split(","):
                stripped = part.strip()
                if stripped and stripped not in normalized:
                    normalized.append(stripped)
        return normalized
