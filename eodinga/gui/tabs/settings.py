from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QInputDialog, QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import SecondaryButton


class SettingsTab(QWidget):
    hotkey_change_requested = Signal(str)
    frameless_changed = Signal(bool)
    always_on_top_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Settings tab")
        self._hotkey_combo = "ctrl+shift+space"
        self._hotkey_available = True
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
        self.remap_hotkey_button.clicked.connect(self._prompt_hotkey_combo)
        self.frameless_checkbox.toggled.connect(self.frameless_changed.emit)
        self.always_on_top_checkbox.toggled.connect(self.always_on_top_changed.emit)
        self.set_hotkey_state(self._hotkey_combo, available=True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.system_theme_checkbox)
        layout.addWidget(self.frameless_checkbox)
        layout.addWidget(self.always_on_top_checkbox)
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.remap_hotkey_button)
        layout.addStretch(1)

    def set_hotkey_combo(self, combo: str) -> None:
        self.set_hotkey_state(combo, available=self._hotkey_available)

    def set_hotkey_state(self, combo: str, *, available: bool) -> None:
        self._hotkey_combo = combo
        self._hotkey_available = available
        status = combo or "disabled"
        suffix = "" if available else " (saved only)"
        self.hotkey_label.setText(f"Launcher hotkey: {status}{suffix}")
        if available:
            description = "Launcher hotkey changes apply immediately."
            button_tooltip = "Enter a global launcher hotkey."
        else:
            description = "Global launcher hotkeys are unavailable in this session. Saved changes apply when supported."
            button_tooltip = "Save a launcher hotkey for a supported session."
        self.hotkey_label.setAccessibleDescription(description)
        self.hotkey_label.setToolTip(description)
        self.remap_hotkey_button.setToolTip(button_tooltip)

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top_checkbox.blockSignals(True)
        self.always_on_top_checkbox.setChecked(enabled)
        self.always_on_top_checkbox.blockSignals(False)

    def set_frameless(self, enabled: bool) -> None:
        self.frameless_checkbox.blockSignals(True)
        self.frameless_checkbox.setChecked(enabled)
        self.frameless_checkbox.blockSignals(False)

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
