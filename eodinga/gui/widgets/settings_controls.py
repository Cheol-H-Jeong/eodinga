from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget


class LauncherSettingsControls(QWidget):
    always_on_top_changed = Signal(bool)

    def __init__(self, *, always_on_top: bool, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher settings controls")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.always_on_top_checkbox = QCheckBox("Keep launcher above other windows", self)
        self.always_on_top_checkbox.setAccessibleName("Launcher always-on-top checkbox")
        self.always_on_top_checkbox.setChecked(always_on_top)
        self.always_on_top_checkbox.toggled.connect(self.always_on_top_changed.emit)
        layout.addWidget(self.always_on_top_checkbox)


__all__ = ["LauncherSettingsControls"]
