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

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(QCheckBox("Use system theme", self))
        layout.addWidget(SecondaryButton("Remap hotkey", self))
        layout.addStretch(1)

