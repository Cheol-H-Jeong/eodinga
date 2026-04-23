from __future__ import annotations

from eodinga.common import IndexingStatus
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from eodinga.gui.widgets import PrimaryButton, StatusChip


class IndexTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Index tab")
        self.setAccessibleDescription("Observe index health and trigger a rebuild.")
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Index", self)
        self.title_label.setProperty("role", "title")
        self.title_label.setAccessibleName("Index tab title")
        body = QLabel("Observe index health, rebuild, and vacuum.", self)
        body.setProperty("role", "secondary")
        body.setAccessibleName("Index tab summary")
        body.setAccessibleDescription("Summarizes index maintenance actions available from this tab.")
        self.status_chip = StatusChip("Idle", self)
        self.status_chip.setAccessibleDescription("Shows whether indexing is idle or currently running.")
        self.progress_label = QLabel("Index is idle.", self)
        self.progress_label.setProperty("role", "secondary")
        self.progress_label.setAccessibleName("Index progress summary")
        self.progress_label.setAccessibleDescription("Reports indexed file progress for the current run.")
        self.rebuild_button = PrimaryButton("Rebuild index", self)
        self.rebuild_button.setAccessibleName("Rebuild index")
        self.rebuild_button.setAccessibleDescription("Rebuild the full search index from the configured roots.")

        layout.addWidget(self.title_label)
        layout.addWidget(body)
        layout.addWidget(self.status_chip)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.rebuild_button)
        layout.addStretch(1)

    def set_indexing_status(self, status: IndexingStatus) -> None:
        if status.phase == "indexing":
            total = status.total_files if status.total_files > 0 else "?"
            root_label = f" · {status.current_root}" if status.current_root is not None else ""
            self.status_chip.setText("Indexing")
            self.progress_label.setText(f"{status.processed_files}/{total} files indexed{root_label}")
            return
        self.status_chip.setText("Idle")
        self.progress_label.setText("Index is idle.")
