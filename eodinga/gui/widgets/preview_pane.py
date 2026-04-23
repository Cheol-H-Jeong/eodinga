from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit
from eodinga.gui.design import SPACE_8
from eodinga.gui.widgets.result_item import _highlight_fts_snippet, highlight_text


class LauncherPreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "title")
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        self.title_label.setWordWrap(True)

        self.path_label = QLabel("", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setTextFormat(Qt.TextFormat.RichText)
        self.path_label.setWordWrap(True)

        self.snippet_label = QLabel("Hover a result to preview its path and snippet.", self)
        self.snippet_label.setProperty("role", "secondary")
        self.snippet_label.setTextFormat(Qt.TextFormat.RichText)
        self.snippet_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label)

    def show_placeholder(self, message: str = "Hover a result to preview its path and snippet.") -> None:
        self.title_label.setText("Preview")
        self.path_label.clear()
        self.snippet_label.setText(message)

    def set_hit(self, hit: SearchHit, query: str) -> None:
        self.title_label.setText(highlight_text(hit.name, query, target="name"))
        self.path_label.setText(highlight_text(str(hit.path), query, target="path"))
        if hit.snippet:
            snippet = (
                _highlight_fts_snippet(hit.snippet)
                if "[" in hit.snippet and "]" in hit.snippet
                else highlight_text(hit.snippet, query, target="snippet")
            )
            self.snippet_label.setText(snippet)
            return
        self.snippet_label.setText("No indexed snippet available for this result yet.")
