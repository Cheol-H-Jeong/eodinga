from __future__ import annotations

from eodinga.common import IndexingStatus
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import PrimaryButton, StatusChip


class IndexTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Index tab")
        layout = QVBoxLayout(self)
        title = QLabel("Index", self)
        title.setProperty("role", "title")
        body = QLabel("Observe index health, rebuild, and vacuum.", self)
        body.setProperty("role", "secondary")
        self.status_chip = StatusChip("Idle", self)
        self.progress_label = QLabel("Index is idle.", self)
        self.progress_label.setProperty("role", "secondary")
        self.rebuild_button = PrimaryButton("Rebuild index", self)
        self.rebuild_button.setAccessibleName("Rebuild index")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.status_chip)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.rebuild_button)
        layout.addStretch(1)

    def set_indexing_status(self, status: IndexingStatus) -> None:
        if status.phase in {"indexing", "paused"}:
            total = status.total_files if status.total_files > 0 else "?"
            root_label = f" · {status.current_root}" if status.current_root is not None else ""
            state = "paused" if status.phase == "paused" else "indexed"
            chip_text = "Paused" if status.phase == "paused" else "Indexing"
            self.status_chip.setText(chip_text)
            self.progress_label.setText(f"{status.processed_files}/{total} files {state}{root_label}")
            return
        self.status_chip.setText("Idle")
        self.progress_label.setText("Index is idle.")
