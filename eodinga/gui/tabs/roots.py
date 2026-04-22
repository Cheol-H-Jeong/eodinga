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

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(PrimaryButton("Add root", self))
        layout.addWidget(SecondaryButton("Remove selected", self))
        layout.addStretch(1)

