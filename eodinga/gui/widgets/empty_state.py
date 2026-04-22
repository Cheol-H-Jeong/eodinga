from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title, self)
        title_label.setProperty("role", "title")
        body_label = QLabel(body, self)
        body_label.setProperty("role", "secondary")
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(body_label)

