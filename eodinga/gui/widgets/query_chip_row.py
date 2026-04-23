from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from eodinga.gui.design import SPACE_4, SPACE_8
from eodinga.gui.widgets.button import SecondaryButton

ChipHandler = Callable[[str], None]


class QueryChipButton(SecondaryButton):
    move_requested = Signal(int)
    jump_requested = Signal(str)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Left:
            self.move_requested.emit(-1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.move_requested.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Home:
            self.jump_requested.emit("start")
            event.accept()
            return
        if event.key() == Qt.Key.Key_End:
            self.jump_requested.emit("end")
            event.accept()
            return
        super().keyPressEvent(event)


class QueryChipRow(QWidget):
    def __init__(self, label: str, *, accessible_name: str, on_chip_clicked: ChipHandler, parent=None) -> None:
        super().__init__(parent)
        self._on_chip_clicked = on_chip_clicked
        self._label_text = label
        self._visible_limit = 5
        self.setAccessibleName(accessible_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self._label = QLabel(label, self)
        self._label.setProperty("role", "secondary")
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._label.setAccessibleName(f"{label} query section")
        layout.addWidget(self._label)

        self._chips_container = QWidget(self)
        self._chips_container.setAccessibleName(f"{label} query chips")
        chips_layout = QHBoxLayout(self._chips_container)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(SPACE_4)
        layout.addWidget(self._chips_container, 1)
        self._overflow_label = QLabel("", self)
        self._overflow_label.setProperty("role", "secondary")
        self._overflow_label.setAccessibleName(f"{label} overflow summary")
        self._overflow_label.setVisible(False)
        layout.addWidget(self._overflow_label)
        layout.addStretch(1)
        self._chips_layout = chips_layout
        self._buttons: list[QueryChipButton] = []
        self.setVisible(False)
        self._refresh_accessibility([])

    def set_queries(self, queries: list[str]) -> None:
        while self._buttons:
            button = self._buttons.pop()
            self._chips_layout.removeWidget(button)
            button.deleteLater()

        visible_queries = queries[: self._visible_limit]
        for query in visible_queries:
            button = QueryChipButton(query, self._chips_container)
            button.setAccessibleName(f"Use query {query}")
            button.setAccessibleDescription(
                f"Apply the {self._label_text.lower()} launcher query. Use Left and Right to move between launcher chips."
            )
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setToolTip(query)
            button.clicked.connect(lambda checked=False, value=query: self._on_chip_clicked(value))
            self._chips_layout.addWidget(button)
            self._buttons.append(button)

        self.setVisible(bool(queries))
        self._refresh_accessibility(queries)
        overflow_count = max(len(queries) - len(visible_queries), 0)
        self._overflow_label.setVisible(overflow_count > 0)
        if overflow_count > 0:
            self._overflow_label.setText(f"+{overflow_count} more")
            self._overflow_label.setToolTip(", ".join(queries))
        else:
            self._overflow_label.clear()
            self._overflow_label.setToolTip("")

    def _refresh_accessibility(self, queries: list[str]) -> None:
        if not queries:
            self.setAccessibleDescription(f"No {self._label_text.lower()} launcher queries are available.")
            self._chips_container.setAccessibleDescription("No launcher query chips are available.")
            self._overflow_label.setAccessibleDescription("No hidden launcher queries are available.")
            return
        summary = ", ".join(queries)
        visible_summary = ", ".join(queries[: self._visible_limit])
        overflow_count = max(len(queries) - self._visible_limit, 0)
        overflow_suffix = (
            f" Showing first {self._visible_limit}; {overflow_count} more are available in the tooltip."
            if overflow_count > 0
            else ""
        )
        self.setAccessibleDescription(f"{len(queries)} {self._label_text.lower()} launcher queries are available: {summary}.{overflow_suffix}")
        self._chips_container.setAccessibleDescription(
            f"Launcher query chips for {visible_summary}. Press Enter or Space to apply a chip."
        )
        if overflow_count > 0:
            self._overflow_label.setAccessibleDescription(
                f"{overflow_count} additional {self._label_text.lower()} launcher queries are hidden from the row."
            )
        else:
            self._overflow_label.setAccessibleDescription("No hidden launcher queries are available.")

    @property
    def buttons(self) -> list[QueryChipButton]:
        return list(self._buttons)

    @property
    def overflow_label(self) -> QLabel:
        return self._overflow_label
