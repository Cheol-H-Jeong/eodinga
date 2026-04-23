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
        self.hotkey_status_label = QLabel("", self)
        self.hotkey_status_label.setProperty("role", "secondary")
        self.hotkey_status_label.setWordWrap(True)
        self.hotkey_status_label.setAccessibleName("Launcher hotkey backend status")
        self.remap_hotkey_button = SecondaryButton("Remap hotkey", self)
        self.remap_hotkey_button.setAccessibleName("Remap hotkey")
        self.remap_hotkey_button.clicked.connect(self._prompt_hotkey_combo)
        self.frameless_checkbox.toggled.connect(self.frameless_changed.emit)
        self.always_on_top_checkbox.toggled.connect(self.always_on_top_changed.emit)
        self.set_hotkey_combo(self._hotkey_combo)
        self.set_hotkey_backend_status(True, self._hotkey_combo)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.system_theme_checkbox)
        layout.addWidget(self.frameless_checkbox)
        layout.addWidget(self.always_on_top_checkbox)
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.hotkey_status_label)
        layout.addWidget(self.remap_hotkey_button)
        layout.addStretch(1)

    def set_hotkey_combo(self, combo: str) -> None:
        self._hotkey_combo = combo
        self.hotkey_label.setText(f"Launcher hotkey: {combo or 'disabled'}")

    def set_hotkey_backend_status(self, available: bool, combo: str) -> None:
        if available:
            if combo:
                self.hotkey_status_label.setText("Global hotkey backend is available. Changes apply immediately.")
            else:
                self.hotkey_status_label.setText("Global hotkey is disabled. Enter a shortcut to enable it immediately.")
            return
        if combo:
            self.hotkey_status_label.setText(
                "Global hotkey backend is unavailable in this session. The shortcut is saved, but it cannot be used live."
            )
            return
        self.hotkey_status_label.setText(
            "Global hotkey backend is unavailable in this session. You can still save a shortcut for a future run."
        )

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
