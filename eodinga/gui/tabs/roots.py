from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import PrimaryButton, SecondaryButton


class RootsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Roots", self)
        title.setProperty("role", "title")
        body = QLabel("Manage indexed paths and exclude patterns.", self)
        body.setProperty("role", "secondary")
        body.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.add_root_button = PrimaryButton("Add root", self)
        self.remove_root_button = SecondaryButton("Remove selected", self)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.add_root_button)
        layout.addWidget(self.remove_root_button)
        layout.addStretch(1)
