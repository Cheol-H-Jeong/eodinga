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
        title.setAccessibleName("About title")
        body = QLabel(f"eodinga {__version__}\nInstant lexical search for files and documents.", self)
        body.setProperty("role", "secondary")
        body.setAccessibleName("About description")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
