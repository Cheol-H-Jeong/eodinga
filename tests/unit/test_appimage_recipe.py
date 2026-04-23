from __future__ import annotations

from pathlib import Path


def test_appimage_recipe_tracks_desktop_and_icon_assets() -> None:
    recipe = Path("packaging/linux/appimage-builder.yml").read_text(encoding="utf-8")

    assert "name: eodinga" in recipe
    assert "icon: eodinga" in recipe
    assert "version: @@APP_VERSION@@" in recipe
    assert "exec: usr/bin/eodinga" in recipe
    assert "exec_args: gui" in recipe
    assert "mkdir -p AppDir/usr/bin AppDir/usr/lib/eodinga" in recipe
    assert "cp -R eodinga AppDir/usr/lib/eodinga/eodinga" in recipe
    assert "      - eodinga" in recipe
    assert "packaging/linux/eodinga.desktop" in recipe
    assert "packaging/linux/eodinga.svg" in recipe


def test_appimage_icon_asset_matches_desktop_name() -> None:
    desktop = Path("packaging/linux/eodinga.desktop").read_text(encoding="utf-8")
    icon = Path("packaging/linux/eodinga.svg").read_text(encoding="utf-8")

    assert "Icon=eodinga" in desktop
    assert "<svg" in icon
    assert "<title" in icon
