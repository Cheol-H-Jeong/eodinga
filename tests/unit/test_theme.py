from __future__ import annotations

from eodinga.gui.theme import apply_theme


def test_apply_theme_skips_reapplying_same_theme(monkeypatch, qapp) -> None:
    calls: list[str] = []

    def _record_palette(app, palette) -> None:
        del app, palette
        calls.append("palette")

    monkeypatch.setattr("eodinga.gui.theme.apply_palette", _record_palette)
    qapp.setProperty("_eodinga_theme_name", None)
    qapp.setProperty("_eodinga_theme_qss", None)

    apply_theme(qapp, "light")
    apply_theme(qapp, "light")

    assert calls == ["palette"]


def test_apply_theme_reapplies_when_theme_changes(monkeypatch, qapp) -> None:
    calls: list[str] = []

    def _record_palette(app, palette) -> None:
        del app, palette
        calls.append("palette")

    monkeypatch.setattr("eodinga.gui.theme.apply_palette", _record_palette)
    qapp.setProperty("_eodinga_theme_name", None)
    qapp.setProperty("_eodinga_theme_qss", None)

    apply_theme(qapp, "light")
    apply_theme(qapp, "dark")

    assert calls == ["palette", "palette"]
