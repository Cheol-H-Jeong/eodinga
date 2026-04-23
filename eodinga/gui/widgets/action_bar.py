from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from eodinga.gui.design import SPACE_8
from eodinga.gui.widgets.button import SecondaryButton


class LauncherActionBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher action bar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self.open_button = SecondaryButton("Open", self)
        self.open_button.setAccessibleName("Open selected result")
        self.reveal_button = SecondaryButton("Reveal", self)
        self.reveal_button.setAccessibleName("Reveal selected result")
        self.copy_path_button = SecondaryButton("Copy path", self)
        self.copy_path_button.setAccessibleName("Copy selected result path")
        self.copy_name_button = SecondaryButton("Copy name", self)
        self.copy_name_button.setAccessibleName("Copy selected result name")
        self.properties_button = SecondaryButton("Properties", self)
        self.properties_button.setAccessibleName("Show selected result properties")

        for button in (
            self.open_button,
            self.reveal_button,
            self.copy_path_button,
            self.copy_name_button,
            self.properties_button,
        ):
            layout.addWidget(button)
        layout.addStretch(1)
        self.set_actions_enabled(False)

    def set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.open_button,
            self.reveal_button,
            self.copy_path_button,
            self.copy_name_button,
            self.properties_button,
        ):
            button.setEnabled(enabled)
