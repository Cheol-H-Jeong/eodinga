from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit


class PreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "title")
        self.path_label = QLabel("", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setWordWrap(True)
        self.snippet_label = QLabel("", self)
        self.snippet_label.setProperty("role", "secondary")
        self.snippet_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label)

        self.clear()

    def clear(self) -> None:
        self.title_label.setText("Preview")
        self.path_label.setText("Select a result to inspect its path and snippet.")
        self.snippet_label.setText("")

    def set_hit(self, hit: SearchHit) -> None:
        self.title_label.setText(hit.name)
        self.path_label.setText(str(hit.path))
        if hit.snippet:
            self.snippet_label.setText(hit.snippet)
            return
        fallback = "No indexed snippet is available for this result yet."
        if hit.ext:
            fallback = f"{fallback} Type: .{hit.ext}"
        self.snippet_label.setText(fallback)
