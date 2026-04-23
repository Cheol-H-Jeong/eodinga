from PySide6.QtWidgets import QWidget, QLabel

from eodinga.common import SearchHit


class PreviewPane(QWidget):
    title_label: QLabel
    path_label: QLabel
    snippet_label: QLabel

    def __init__(self, parent = ...) -> None: ...
    def clear(self) -> None: ...
    def set_hit(self, hit: SearchHit) -> None: ...
