from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from eodinga.gui.design import (
    BORDER_1,
    BUTTON_HEIGHT,
    FOCUS_RING,
    FONT_11,
    FONT_13,
    FONT_15,
    FONT_18,
    FONT_24,
    PALETTES,
    Palette,
    RADIUS_12,
    RADIUS_18,
    SPACE_16,
    SPACE_8,
)


def build_qss(palette: Palette) -> str:
    return f"""
    QWidget {{
        background-color: {palette.app_bg};
        color: {palette.text};
        font-size: {FONT_13}px;
    }}
    QWidget#surface {{
        background-color: {palette.surface};
        border: {BORDER_1}px solid {palette.border};
        border-radius: {RADIUS_18}px;
    }}
    QTabWidget::pane {{
        border: {BORDER_1}px solid {palette.border};
        border-radius: {RADIUS_12}px;
        background: {palette.surface};
    }}
    QTabBar::tab {{
        background: {palette.surface_muted};
        color: {palette.text_muted};
        padding: {SPACE_8}px {SPACE_16}px;
        border-top-left-radius: {RADIUS_12}px;
        border-top-right-radius: {RADIUS_12}px;
        margin-right: 4px;
    }}
    QTabBar::tab:selected {{
        background: {palette.surface};
        color: {palette.text};
    }}
    QPushButton {{
        min-height: {BUTTON_HEIGHT}px;
        border-radius: {RADIUS_12}px;
        padding: 0 {SPACE_16}px;
        font-size: {FONT_13}px;
        border: {BORDER_1}px solid {palette.border};
        background: {palette.surface_muted};
        color: {palette.text};
    }}
    QPushButton[variant="primary"] {{
        background: {palette.accent};
        color: {palette.accent_text};
        border-color: {palette.accent};
        font-size: {FONT_15}px;
    }}
    QPushButton[variant="secondary"] {{
        background: {palette.surface};
        color: {palette.text};
    }}
    QLineEdit {{
        min-height: 44px;
        padding: 0 {SPACE_16}px;
        border-radius: {RADIUS_12}px;
        border: {BORDER_1}px solid {palette.border};
        background: {palette.surface};
        selection-background-color: {palette.accent};
        selection-color: {palette.accent_text};
        font-size: {FONT_18}px;
    }}
    QLineEdit:focus, QPushButton:focus {{
        border: {FOCUS_RING}px solid {palette.focus};
    }}
    QLabel[role="secondary"] {{
        color: {palette.text_muted};
        font-size: {FONT_11}px;
    }}
    QLabel[role="title"] {{
        font-size: {FONT_24}px;
        font-weight: 600;
    }}
    QLabel[chip="true"] {{
        background: {palette.surface_muted};
        border-radius: 10px;
        padding: 4px 10px;
        border: {BORDER_1}px solid {palette.border};
    }}
    QPushButton[chip="true"] {{
        min-height: 0;
        padding: 4px 10px;
        border-radius: 10px;
        background: {palette.surface_muted};
        border: {BORDER_1}px solid {palette.border};
        color: {palette.text};
        font-size: {FONT_11}px;
    }}
    QPushButton[chip="true"][chipKind="pinned"] {{
        background: {palette.surface};
    }}
    QListView {{
        background: transparent;
        border: none;
    }}
    """


def apply_palette(app: QApplication, palette: Palette) -> None:
    qt_palette = QPalette()
    qt_palette.setColor(QPalette.ColorRole.Window, QColor(palette.app_bg))
    qt_palette.setColor(QPalette.ColorRole.Base, QColor(palette.surface))
    qt_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(palette.surface_muted))
    qt_palette.setColor(QPalette.ColorRole.Button, QColor(palette.surface_muted))
    qt_palette.setColor(QPalette.ColorRole.ButtonText, QColor(palette.text))
    qt_palette.setColor(QPalette.ColorRole.Text, QColor(palette.text))
    qt_palette.setColor(QPalette.ColorRole.WindowText, QColor(palette.text))
    qt_palette.setColor(QPalette.ColorRole.Highlight, QColor(palette.accent))
    qt_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(palette.accent_text))
    app.setPalette(qt_palette)


def apply_theme(app: QApplication, theme_name: str = "light") -> Palette:
    palette = PALETTES.get(theme_name, PALETTES["light"])
    apply_palette(app, palette)
    app.setStyleSheet(build_qss(palette))
    return palette
