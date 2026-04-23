from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QInputDialog, QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import SecondaryButton


class SettingsTab(QWidget):
    hotkey_change_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Settings tab")
        self._hotkey_combo = "ctrl+shift+space"
        layout = QVBoxLayout(self)
        title = QLabel("Settings", self)
        title.setProperty("role", "title")
        body = QLabel("Configure the hotkey, theme, and launcher behavior.", self)
        body.setProperty("role", "secondary")
        self.system_theme_checkbox = QCheckBox("Use system theme", self)
        self.system_theme_checkbox.setAccessibleName("Use system theme")
        self.hotkey_label = QLabel("", self)
        self.hotkey_label.setProperty("role", "secondary")
        self.hotkey_label.setAccessibleName("Current launcher hotkey")
        self.remap_hotkey_button = SecondaryButton("Remap hotkey", self)
        self.remap_hotkey_button.setAccessibleName("Remap hotkey")
        self.remap_hotkey_button.clicked.connect(self._prompt_hotkey_combo)
        self.set_hotkey_combo(self._hotkey_combo)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.system_theme_checkbox)
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.remap_hotkey_button)
        layout.addStretch(1)

    def set_hotkey_combo(self, combo: str) -> None:
        self._hotkey_combo = combo
        self.hotkey_label.setText(f"Launcher hotkey: {combo}")

    def _prompt_hotkey_combo(self) -> None:
        combo, accepted = QInputDialog.getText(
            self,
            "Remap launcher hotkey",
            "Enter a launcher hotkey:",
            text=self._hotkey_combo,
        )
        normalized = combo.strip()
        if not accepted or not normalized:
            return
        self.hotkey_change_requested.emit(normalized)
