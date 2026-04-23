from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga import __version__


class AboutTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("About tab")
        layout = QVBoxLayout(self)
        title = QLabel("About", self)
        title.setProperty("role", "title")
        title.setAccessibleName("About tab title")
        body = QLabel(f"eodinga {__version__}\nInstant lexical search for files and documents.", self)
        body.setProperty("role", "secondary")
        body.setWordWrap(True)
        body.setAccessibleName("About tab description")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
