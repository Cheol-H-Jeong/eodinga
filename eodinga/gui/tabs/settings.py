from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.config import AppConfig
from eodinga.gui.widgets import LauncherSettingsControls, SecondaryButton


class SettingsTab(QWidget):
    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        launcher_window=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Settings", self)
        title.setProperty("role", "title")
        body = QLabel("Configure the hotkey, theme, and launcher behavior.", self)
        body.setProperty("role", "secondary")
        self.controls = LauncherSettingsControls(
            always_on_top=config.launcher.always_on_top if config is not None else False,
            parent=self,
        )
        self.controls.always_on_top_changed.connect(
            lambda enabled: launcher_window.set_always_on_top(enabled)
            if launcher_window is not None
            else None
        )
        remap_button = SecondaryButton("Remap hotkey", self)
        remap_button.setAccessibleName("Launcher remap hotkey button")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.controls)
        layout.addWidget(remap_button)
        layout.addStretch(1)
