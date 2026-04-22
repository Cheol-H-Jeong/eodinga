from __future__ import annotations

# Adapted from autoshelf design tokens:
# /home/cheol/projects/autoshelf/autoshelf/gui/design.py

from dataclasses import dataclass

SPACE_4 = 4
SPACE_8 = 8
SPACE_16 = 16
SPACE_24 = 24
SPACE_32 = 32

FONT_11 = 11
FONT_13 = 13
FONT_15 = 15
FONT_18 = 18
FONT_24 = 24

RADIUS_12 = 12
RADIUS_18 = 18
BORDER_1 = 1
FOCUS_RING = 2
BUTTON_HEIGHT = 40
MOTION_FAST_MS = 120
MOTION_LAYOUT_MS = 180
MOTION_DEBOUNCE_MS = 30


@dataclass(frozen=True)
class Palette:
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    surface: str
    surface_muted: str
    surface_raised: str
    app_bg: str
    border: str
    text: str
    text_muted: str
    success: str
    warning: str
    danger: str
    focus: str
    shadow: str


LIGHT = Palette(
    accent="#0F766E",
    accent_hover="#0D9488",
    accent_pressed="#115E59",
    accent_text="#F8FAFC",
    surface="#FFFFFF",
    surface_muted="#F3F4F6",
    surface_raised="#FCFCFD",
    app_bg="#EEF2F0",
    border="#CBD5D1",
    text="#111827",
    text_muted="#4B5563",
    success="#047857",
    warning="#92400E",
    danger="#B91C1C",
    focus="#0F766E",
    shadow="rgba(15, 23, 42, 0.14)",
)

DARK = Palette(
    accent="#5EEAD4",
    accent_hover="#99F6E4",
    accent_pressed="#2DD4BF",
    accent_text="#0B1B1A",
    surface="#172120",
    surface_muted="#1F2D2C",
    surface_raised="#223231",
    app_bg="#101817",
    border="#314341",
    text="#F3F4F6",
    text_muted="#D1D5DB",
    success="#6EE7B7",
    warning="#FBBF24",
    danger="#FCA5A5",
    focus="#5EEAD4",
    shadow="rgba(15, 23, 42, 0.45)",
)

PALETTES = {"light": LIGHT, "dark": DARK}

TEXT_ON_BG_PAIRS = (
    ("text", "surface"),
    ("text", "surface_muted"),
    ("text", "surface_raised"),
    ("text", "app_bg"),
    ("text_muted", "surface"),
    ("accent_text", "accent"),
    ("success", "surface"),
    ("warning", "surface"),
    ("danger", "surface"),
)

