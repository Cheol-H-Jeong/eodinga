from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit


class PreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("surface")
        self.setMinimumWidth(240)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "title")
        self.path_label = QLabel("Hover or select a result to inspect its location and snippet.", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.snippet_label = QLabel("No result selected.", self)
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label)
        layout.addStretch(1)

    def clear_preview(self) -> None:
        self.title_label.setText("Preview")
        self.path_label.setText("Hover or select a result to inspect its location and snippet.")
        self.snippet_label.setText("No result selected.")

    def set_hit(self, hit: SearchHit) -> None:
        self.title_label.setText(hit.name)
        self.path_label.setText(str(hit.path))
        self.snippet_label.setText(hit.snippet or "No content snippet indexed for this file.")
