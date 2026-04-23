from __future__ import annotations

from pathlib import Path


def test_deb_recipe_tracks_desktop_icon_and_docs_assets() -> None:
    desktop = Path("packaging/linux/eodinga.desktop").read_text(encoding="utf-8")
    icon = Path("packaging/linux/eodinga.svg").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    control = Path("packaging/linux/debian/control").read_text(encoding="utf-8")
    debian_changelog = Path("packaging/linux/debian/changelog").read_text(encoding="utf-8")

    assert "Name=eodinga" in desktop
    assert "Exec=eodinga gui" in desktop
    assert "Icon=eodinga" in desktop
    assert "Categories=Utility;FileTools;" in desktop
    assert "<svg" in icon
    assert "<title" in icon
    assert "# Changelog" in changelog
    assert "eodinga (@@APP_VERSION@@-1) unstable; urgency=medium" in debian_changelog
    assert "Source: eodinga" in control
    assert "Package: eodinga" in control
    assert "Version: @@APP_VERSION@@" in control
    assert "Architecture: @@TARGET_ARCH@@" in control
    assert "Depends: python3 (>= 3.11)" in control
    assert "Description: Instant lexical file search for Windows and Linux" in control
