from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import SecondaryButton


class SettingsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Settings", self)
        title.setProperty("role", "title")
        body = QLabel("Configure the hotkey, theme, and launcher behavior.", self)
        body.setProperty("role", "secondary")
        self.use_system_theme_checkbox = QCheckBox("Use system theme", self)
        self.use_system_theme_checkbox.setAccessibleName("Use system theme")
        self.remap_hotkey_button = SecondaryButton("Remap hotkey", self)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.use_system_theme_checkbox)
        layout.addWidget(self.remap_hotkey_button)
        layout.addStretch(1)
