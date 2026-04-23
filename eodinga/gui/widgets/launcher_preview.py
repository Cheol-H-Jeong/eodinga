from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from eodinga.common import SearchHit
from eodinga.gui.design import SPACE_4, SPACE_8, SPACE_16
from eodinga.gui.widgets.button import SecondaryButton
from eodinga.gui.widgets.result_item import format_preview_html

_PREVIEW_CACHE_LIMIT = 64
_PREVIEW_READ_BYTES = 8192


def _normalize_preview_text(raw: str) -> str:
    lines = [line.strip() for line in raw.replace("\r", "\n").split("\n")]
    collapsed = " ".join(line for line in lines if line)
    return collapsed[:600].strip()


def _load_preview_fallback(path: Path) -> str | None:
    try:
        if path.is_dir():
            return "This result is a folder. Open or reveal it to inspect its contents."
        if not path.is_file():
            return None
        sample = path.read_bytes()[:_PREVIEW_READ_BYTES]
    except OSError:
        return None
    if not sample:
        return "This file is empty."
    if b"\x00" in sample:
        return "Binary file preview is unavailable for this result."
    decoded = sample.decode("utf-8", errors="replace")
    normalized = _normalize_preview_text(decoded)
    return normalized or "No readable preview text is available for this result."


class LauncherPreviewPane(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_hit: SearchHit | None = None
        self._query = ""
        self._preview_cache: OrderedDict[Path, str] = OrderedDict()
        self.setAccessibleName("Launcher preview pane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_8)

        eyebrow = QLabel("Preview", self)
        eyebrow.setProperty("role", "secondary")
        eyebrow.setAccessibleName("Launcher preview heading")
        self.title_label = QLabel(self)
        self.title_label.setWordWrap(True)
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.title_label.setAccessibleName("Previewed result name")
        self.path_label = QLabel(self)
        self.path_label.setProperty("role", "secondary")
        self.path_label.setWordWrap(True)
        self.path_label.setTextFormat(Qt.TextFormat.RichText)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setAccessibleName("Previewed result path")
        self.snippet_label = QLabel(self)
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setTextFormat(Qt.TextFormat.RichText)
        self.snippet_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.snippet_label.setMinimumWidth(220)
        self.snippet_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.snippet_label.setAccessibleName("Previewed result snippet")

        layout.addWidget(eyebrow)
        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.snippet_label, 1)

        self.set_hit(None)

    def set_query(self, query: str) -> None:
        self._query = query
        self.set_hit(self._current_hit)

    def set_hit(self, hit: SearchHit | None) -> None:
        self._current_hit = hit
        preview_hit = self._preview_hit(hit)
        title, path_text, snippet = format_preview_html(preview_hit, self._query)
        self.title_label.setText(title)
        self.path_label.setText(path_text)
        self.snippet_label.setText(snippet)

    def _preview_hit(self, hit: SearchHit | None) -> SearchHit | None:
        if hit is None or (hit.snippet or "").strip():
            return hit
        fallback = self._preview_cache.get(hit.path)
        if fallback is None:
            fallback = _load_preview_fallback(hit.path)
            if fallback is None:
                return hit
            self._preview_cache[hit.path] = fallback
            while len(self._preview_cache) > _PREVIEW_CACHE_LIMIT:
                self._preview_cache.popitem(last=False)
        else:
            self._preview_cache.move_to_end(hit.path)
        return hit.model_copy(update={"snippet": fallback})


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
        self.open_button.setAccessibleDescription("Open the selected result with Enter.")
        self.reveal_button.setAccessibleName("Reveal selected result")
        self.reveal_button.setAccessibleDescription("Reveal the selected result with Ctrl+Enter.")
        self.copy_path_button.setAccessibleName("Copy selected path")
        self.copy_path_button.setAccessibleDescription("Copy the selected result path with Alt+C.")
        self.copy_name_button.setAccessibleName("Copy selected name")
        self.copy_name_button.setAccessibleDescription("Copy the selected result name with Alt+N.")
        self.properties_button.setAccessibleName("Show selected properties")
        self.properties_button.setAccessibleDescription("Open selected result properties with Shift+Enter.")

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
