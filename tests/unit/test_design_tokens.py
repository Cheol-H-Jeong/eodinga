from __future__ import annotations

from eodinga.gui.design import PALETTES, TEXT_ON_BG_PAIRS


def _relative_luminance(hex_color: str) -> float:
    rgb = [int(hex_color[index : index + 2], 16) / 255.0 for index in (1, 3, 5)]

    def channel(value: float) -> float:
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = [channel(value) for value in rgb]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    l1 = _relative_luminance(foreground)
    l2 = _relative_luminance(background)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_design_palette_contrast_pairs_meet_wcag_aa() -> None:
    for palette in PALETTES.values():
        for text_key, background_key in TEXT_ON_BG_PAIRS:
            contrast = _contrast_ratio(getattr(palette, text_key), getattr(palette, background_key))
            assert contrast >= 4.5, f"{text_key} on {background_key} failed with {contrast:.2f}"
