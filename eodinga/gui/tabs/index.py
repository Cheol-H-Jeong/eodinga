from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import PrimaryButton, StatusChip


class IndexTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Index", self)
        title.setProperty("role", "title")
        body = QLabel("Observe index health, rebuild, and vacuum.", self)
        body.setProperty("role", "secondary")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(StatusChip("Idle", self))
        layout.addWidget(PrimaryButton("Rebuild index", self))
        layout.addStretch(1)

