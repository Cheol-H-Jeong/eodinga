from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import PrimaryButton, SecondaryButton


class RootsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Roots tab")
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Roots", self)
        self.title_label.setProperty("role", "title")
        self.title_label.setAccessibleName("Roots tab title")
        self.body_label = QLabel("Manage indexed paths and exclude patterns.", self)
        self.body_label.setProperty("role", "secondary")
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.body_label.setAccessibleName("Roots tab guidance")
        self.add_root_button = PrimaryButton("Add root", self)
        self.add_root_button.setAccessibleName("Add root")
        self.remove_root_button = SecondaryButton("Remove selected", self)
        self.remove_root_button.setAccessibleName("Remove selected root")

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.add_root_button)
        layout.addWidget(self.remove_root_button)
        layout.addStretch(1)
