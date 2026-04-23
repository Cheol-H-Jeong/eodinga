from __future__ import annotations

from eodinga.gui.theme import PALETTES, apply_theme, build_qss


def test_apply_theme_is_idempotent_for_same_theme(monkeypatch, qapp) -> None:
    calls: list[str] = []
    expected_qss = build_qss(PALETTES["light"])
    qapp.setStyleSheet("")
    qapp.setProperty("_eodinga_theme_name", None)

    original_set_stylesheet = qapp.setStyleSheet

    def record_stylesheet(stylesheet: str) -> None:
        calls.append(stylesheet)
        original_set_stylesheet(stylesheet)

    monkeypatch.setattr(qapp, "setStyleSheet", record_stylesheet)

    apply_theme(qapp, "light")
    apply_theme(qapp, "light")

    assert calls == [expected_qss]
    assert qapp.property("_eodinga_theme_name") == "light"
