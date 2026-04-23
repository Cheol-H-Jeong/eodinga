from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit


class PreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "title")
        self.path_label = QLabel("", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.meta_label = QLabel("", self)
        self.meta_label.setProperty("role", "secondary")
        self.body_label = QLabel("Select a result to inspect its path and snippet.", self)
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.body_label, 1)

        self.clear()

    def clear(self) -> None:
        self.title_label.setText("Preview")
        self.path_label.clear()
        self.meta_label.clear()
        self.body_label.setText("Select a result to inspect its path and snippet.")

    def set_hit(self, hit: SearchHit | None) -> None:
        if hit is None:
            self.clear()
            return
        self.title_label.setText(hit.name)
        self.path_label.setText(str(hit.path))
        self.meta_label.setText(self._meta_text(hit))
        self.body_label.setText(hit.snippet or f"Folder: {hit.parent_path}")

    @staticmethod
    def _meta_text(hit: SearchHit) -> str:
        parts: list[str] = []
        if hit.ext:
            parts.append(hit.ext.upper())
        if hit.path.suffix:
            parts.append(hit.path.suffix)
        if hit.parent_path != Path("."):
            parts.append(f"Parent: {hit.parent_path.name or hit.parent_path}")
        return " · ".join(parts)
