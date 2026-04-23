from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher empty state")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setProperty("role", "title")
        self.title_label.setAccessibleName("Launcher empty state title")
        self.body_label = QLabel(body, self)
        self.body_label.setProperty("role", "secondary")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_label.setAccessibleName("Launcher empty state guidance")
        self.details_label = QLabel("", self)
        self.details_label.setProperty("role", "secondary")
        self.details_label.setWordWrap(True)
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_label.setVisible(False)
        self.details_label.setAccessibleName("Launcher indexing details")

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.details_label)

    def set_content(self, title: str, body: str, details: str = "") -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.details_label.setText(details)
        self.details_label.setVisible(bool(details))
        self.setAccessibleDescription(" ".join(part for part in (title, body, details) if part))
