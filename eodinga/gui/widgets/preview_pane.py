from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit
from eodinga.gui.design import SPACE_16, SPACE_8


class LauncherPreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACE_8, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel("Preview", self)
        self.title_label.setProperty("role", "secondary")
        self.path_label = QLabel("", self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(self.path_label.textInteractionFlags())
        self.snippet_label = QLabel("", self)
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setMinimumHeight(SPACE_16 * 3)
        self.snippet_label.setStyleSheet("padding: 10px; border-radius: 12px; background: rgba(148, 163, 184, 0.12);")

        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label)
        self.clear_preview()

    def clear_preview(self) -> None:
        self.title_label.setText("Preview")
        self.path_label.setText("")
        self.snippet_label.setText("Hover or select a result to inspect its path and indexed snippet.")

    def set_hit(self, hit: SearchHit) -> None:
        self.title_label.setText(hit.name)
        self.path_label.setText(str(hit.path))
        self.snippet_label.setText(hit.snippet or "No indexed content preview is available for this result.")


__all__ = ["LauncherPreviewPane"]
