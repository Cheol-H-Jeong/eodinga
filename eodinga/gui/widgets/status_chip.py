from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class StatusChip(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setProperty("chip", True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName("Status indicator")
