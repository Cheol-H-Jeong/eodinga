from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QTextBrowser, QWidget

from eodinga.common import SearchHit


def _render_preview(hit: SearchHit | None) -> str:
    if hit is None:
        return (
            "<div style='font-size:13px; color:#6B7280'>"
            "Preview the selected result here. Use the arrow keys or hover a row to inspect it."
            "</div>"
        )
    snippet = escape(hit.snippet) if hit.snippet else "No indexed content preview available."
    return (
        f"<div style='font-size:14px; font-weight:700; color:#111827'>{escape(hit.name)}</div>"
        f"<div style='margin-top:4px; font-size:11px; color:#6B7280'>{escape(str(hit.path))}</div>"
        f"<div style='margin-top:10px; font-size:12px; color:#374151'>{snippet}</div>"
    )


class PreviewPane(QTextBrowser):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Launcher result preview")
        self.setObjectName("launcherPreview")
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setMinimumHeight(112)
        self.setHtml(_render_preview(None))

    def set_hit(self, hit: SearchHit | None) -> None:
        self.setHtml(_render_preview(hit))
