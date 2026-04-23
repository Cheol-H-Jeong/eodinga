from __future__ import annotations

from eodinga.gui.theme import apply_theme


def test_apply_theme_is_stable_when_reapplied_to_same_application(qapp) -> None:
    first = apply_theme(qapp, "light")
    first_qss = qapp.styleSheet()

    second = apply_theme(qapp, "light")

    assert second == first
    assert qapp.styleSheet() == first_qss
    assert qapp.property("eodinga_theme_name") == "light"
