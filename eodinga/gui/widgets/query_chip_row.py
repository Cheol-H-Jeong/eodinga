from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from eodinga.gui.design import SPACE_4, SPACE_8
from eodinga.gui.widgets.button import SecondaryButton

ChipHandler = Callable[[str], None]
FocusHandler = Callable[[], None]


class QueryChipRow(QWidget):
    def __init__(
        self,
        label: str,
        *,
        accessible_name: str,
        on_chip_clicked: ChipHandler,
        on_escape: FocusHandler | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_chip_clicked = on_chip_clicked
        self._on_escape = on_escape
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
            button.installEventFilter(self)
            self._chips_layout.addWidget(button)
            self._buttons.append(button)

        self.setVisible(bool(queries))

    def focus_first(self) -> bool:
        return self._focus_button(0)

    def focus_last(self) -> bool:
        return self._focus_button(len(self._buttons) - 1)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched not in self._buttons or event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key_event = cast(QKeyEvent, event)
        button = cast(SecondaryButton, watched)
        index = self._buttons.index(button)
        if key_event.key() in {Qt.Key.Key_Right, Qt.Key.Key_Down}:
            return self._focus_button((index + 1) % len(self._buttons))
        if key_event.key() in {Qt.Key.Key_Left, Qt.Key.Key_Up}:
            return self._focus_button((index - 1) % len(self._buttons))
        if key_event.key() == Qt.Key.Key_Home:
            return self._focus_button(0)
        if key_event.key() == Qt.Key.Key_End:
            return self._focus_button(len(self._buttons) - 1)
        if key_event.key() == Qt.Key.Key_Escape and self._on_escape is not None:
            self._on_escape()
            return True
        return super().eventFilter(watched, event)

    def _focus_button(self, index: int) -> bool:
        if not self._buttons:
            return False
        self._buttons[index].setFocus()
        return True

    @property
    def buttons(self) -> list[SecondaryButton]:
        return list(self._buttons)
