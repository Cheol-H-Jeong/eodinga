from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga import __version__


class AboutTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("About tab")
        self.setAccessibleDescription("Show the app version and a short product summary.")
        layout = QVBoxLayout(self)
        self.title_label = QLabel("About", self)
        self.title_label.setProperty("role", "title")
        self.title_label.setAccessibleName("About tab title")
        self.body_label = QLabel(f"eodinga {__version__}\nInstant lexical search for files and documents.", self)
        self.body_label.setProperty("role", "secondary")
        self.body_label.setWordWrap(True)
        self.body_label.setAccessibleName("About tab summary")
        self.body_label.setAccessibleDescription("States the current app version and a brief product description.")

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addStretch(1)
