from __future__ import annotations

from pathlib import Path


def test_deb_recipe_tracks_desktop_icon_and_docs_assets() -> None:
    desktop = Path("packaging/linux/eodinga.desktop").read_text(encoding="utf-8")
    icon = Path("packaging/linux/eodinga.svg").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    control = Path("packaging/linux/debian/control").read_text(encoding="utf-8")
    postrm = Path("packaging/linux/debian/postrm").read_text(encoding="utf-8")

    assert "Name=eodinga" in desktop
    assert "Exec=eodinga gui" in desktop
    assert "Icon=eodinga" in desktop
    assert "Categories=Utility;FileTools;" in desktop
    assert "<svg" in icon
    assert "<title" in icon
    assert "# Changelog" in changelog
    assert "Source: eodinga" in control
    assert "Package: eodinga" in control
    assert "Version: @@APP_VERSION@@" in control
    assert "Architecture: @@TARGET_ARCH@@" in control
    assert "Depends: python3 (>= 3.11)" in control
    assert "Description: Instant lexical file search for Windows and Linux" in control
    assert 'case "$1" in' in postrm
    assert "purge)" in postrm
    assert "rm -rf /var/lib/eodinga /etc/eodinga" in postrm
    assert "/home/" not in postrm
