from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit


class LauncherPreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")
        self.setMinimumWidth(260)
        self.setObjectName("surface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "title")
        self.path_label = QLabel("", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.snippet_label = QLabel("", self)
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.snippet_label.setTextFormat(Qt.TextFormat.PlainText)
        self.hint_label = QLabel("", self)
        self.hint_label.setProperty("role", "secondary")
        self.hint_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label, 1)
        layout.addWidget(self.hint_label)

        self.set_hit(None)

    def set_hit(self, hit: SearchHit | None) -> None:
        if hit is None:
            self.title_label.setText("Preview")
            self.path_label.setText("Hover or select a result to inspect it here.")
            self.snippet_label.setText("")
            self.hint_label.setText("Text snippets appear when the index has extracted content for the selected file.")
            return
        self.title_label.setText(hit.name)
        self.path_label.setText(str(hit.path))
        self.snippet_label.setText(hit.snippet or "No extracted text preview is available for this result.")
        self.hint_label.setText(f"Parent folder: {hit.parent_path}")
