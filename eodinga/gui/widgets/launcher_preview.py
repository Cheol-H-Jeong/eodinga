from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit
from eodinga.gui.design import SPACE_4, SPACE_8, SPACE_16
from eodinga.gui.widgets.button import SecondaryButton


def _preview_text(hit: SearchHit | None) -> tuple[str, str, str]:
    if hit is None:
        return (
            "No preview yet",
            "Hover a result or move the selection to inspect it before opening.",
            "Snippets and target paths appear here when a result is available.",
        )
    path_text = str(hit.path)
    snippet = (hit.snippet or "").strip()
    if not snippet:
        snippet = "No indexed content snippet is available for this result."
    return hit.name, path_text, snippet


class LauncherPreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher preview pane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_8)

        eyebrow = QLabel("Preview", self)
        eyebrow.setProperty("role", "secondary")
        eyebrow.setAccessibleName("Preview heading")
        self.title_label = QLabel(self)
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.title_label.setAccessibleName("Preview title")
        self.path_label = QLabel(self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setAccessibleName("Preview path")
        self.snippet_label = QLabel(self)
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.snippet_label.setMinimumWidth(220)
        self.snippet_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.snippet_label.setAccessibleName("Preview snippet")

        layout.addWidget(eyebrow)
        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label, 1)

        self.set_hit(None)

    def set_hit(self, hit: SearchHit | None) -> None:
        title, path_text, snippet = _preview_text(hit)
        self.title_label.setText(title)
        self.path_label.setText(path_text)
        self.snippet_label.setText(snippet)


class LauncherActionBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher action bar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_4)

        self.open_button = SecondaryButton("Open", self)
        self.reveal_button = SecondaryButton("Reveal", self)
        self.copy_path_button = SecondaryButton("Copy Path", self)
        self.copy_name_button = SecondaryButton("Copy Name", self)
        self.properties_button = SecondaryButton("Properties", self)

        self.open_button.setAccessibleName("Open selected result")
        self.reveal_button.setAccessibleName("Reveal selected result")
        self.copy_path_button.setAccessibleName("Copy selected path")
        self.copy_name_button.setAccessibleName("Copy selected name")
        self.properties_button.setAccessibleName("Show selected properties")
        self.open_button.setToolTip("Open the selected result (Enter)")
        self.reveal_button.setToolTip("Reveal the selected result in its folder (Ctrl+Enter)")
        self.copy_path_button.setToolTip("Copy the selected path (Alt+C)")
        self.copy_name_button.setToolTip("Copy the selected name (Alt+N)")
        self.properties_button.setToolTip("Show properties for the selected result (Shift+Enter)")

        for button in (
            self.open_button,
            self.reveal_button,
            self.copy_path_button,
            self.copy_name_button,
            self.properties_button,
        ):
            layout.addWidget(button)

    def set_enabled(self, enabled: bool) -> None:
        self.open_button.setEnabled(enabled)
        self.reveal_button.setEnabled(enabled)
        self.copy_path_button.setEnabled(enabled)
        self.copy_name_button.setEnabled(enabled)
        self.properties_button.setEnabled(enabled)


__all__ = ["LauncherActionBar", "LauncherPreviewPane"]
