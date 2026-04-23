from __future__ import annotations

from pathlib import Path


def test_inno_script_contains_required_fields() -> None:
    script = Path("packaging/windows/eodinga.iss").read_text(encoding="utf-8")
    assert '#define AppId "{{B4D25A04-71A1-45A2-A0BB-7B3F612E9E68}"' in script
    assert '#define AppVersion "@@APP_VERSION@@"' in script
    assert '#define ProjectRoot "..\\\\..\\\\.."' in script
    assert "AppVersion={#AppVersion}" in script
    assert "OutputDir=." in script
    assert "OutputBaseFilename=eodinga-{#AppVersion}-win-x64-setup" in script
    assert r"LicenseFile={#ProjectRoot}\LICENSE" in script
    assert r"UninstallDisplayIcon={app}\@@GUI_EXE_NAME@@" in script
    assert 'Name: "english"' in script
    assert 'Name: "korean"' in script
    assert 'Name: "autostart"' in script
    assert '@@GUI_DIST_NAME@@' in script
    assert '@@CLI_DIST_NAME@@' in script
    assert '@@GUI_EXE_NAME@@' in script
    assert r'Source: "{#ProjectRoot}\\dist\\@@GUI_DIST_NAME@@\\*"' in script
    assert r'Source: "{#ProjectRoot}\\dist\\@@CLI_DIST_NAME@@\\*"' in script
    assert 'Name: "{userdesktop}\\\\eodinga"; Filename: "{app}\\\\@@GUI_EXE_NAME@@"; Tasks: desktopicon' in script
    assert "{commondesktop}" not in script
    assert 'Subkey: "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run"' in script
    assert 'ValueName: "eodinga"' in script
    assert "procedure PurgeUserState();" in script
    assert "DelTree(ExpandConstant('{localappdata}\\\\eodinga'), True, True, True);" in script
    assert "DelTree(ExpandConstant('{userappdata}\\\\eodinga'), True, True, True);" in script
