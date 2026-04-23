from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from eodinga.gui.design import SPACE_4, SPACE_8
from eodinga.gui.widgets.button import SecondaryButton

ChipHandler = Callable[[str], None]


class QueryChipRow(QWidget):
    def __init__(self, label: str, *, accessible_name: str, on_chip_clicked: ChipHandler, parent=None) -> None:
        super().__init__(parent)
        self._on_chip_clicked = on_chip_clicked
        self.setAccessibleName(accessible_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self._label = QLabel(label, self)
        self._label.setProperty("role", "secondary")
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label)

        self._chips_container = QWidget(self)
        chips_layout = QHBoxLayout(self._chips_container)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(SPACE_4)
        layout.addWidget(self._chips_container, 1)
        layout.addStretch(1)
        self._chips_layout = chips_layout
        self._buttons: list[SecondaryButton] = []
        self.setVisible(False)

    def set_queries(self, queries: list[str]) -> None:
        while self._buttons:
            button = self._buttons.pop()
            self._chips_layout.removeWidget(button)
            button.deleteLater()

        for query in queries:
            button = SecondaryButton(query, self._chips_container)
            button.setAccessibleName(f"Use query {query}")
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, value=query: self._on_chip_clicked(value))
            self._chips_layout.addWidget(button)
            self._buttons.append(button)

        self.setVisible(bool(queries))

    @property
    def buttons(self) -> list[SecondaryButton]:
        return list(self._buttons)


class StaticChipRow(QWidget):
    def __init__(self, label: str, *, accessible_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setAccessibleName(accessible_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_8)

        self._label = QLabel(label, self)
        self._label.setProperty("role", "secondary")
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label)

        self._chips_container = QWidget(self)
        chips_layout = QHBoxLayout(self._chips_container)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(SPACE_4)
        layout.addWidget(self._chips_container, 1)
        layout.addStretch(1)
        self._chips_layout = chips_layout
        self._labels: list[QLabel] = []
        self.setVisible(False)

    def set_chips(self, chips: list[str]) -> None:
        while self._labels:
            label = self._labels.pop()
            self._chips_layout.removeWidget(label)
            label.deleteLater()

        for chip in chips:
            label = QLabel(chip, self._chips_container)
            label.setProperty("chip", True)
            label.setProperty("role", "secondary")
            label.setAccessibleName(f"Active filter {chip}")
            self._chips_layout.addWidget(label)
            self._labels.append(label)

        self.setVisible(bool(chips))

    @property
    def labels(self) -> list[QLabel]:
        return list(self._labels)
