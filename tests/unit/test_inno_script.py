from __future__ import annotations

from pathlib import Path


def test_inno_script_contains_required_fields() -> None:
    script = Path("packaging/windows/eodinga.iss").read_text(encoding="utf-8")
    assert "AppVersion={#AppVersion}" in script
    assert "OutputBaseFilename=eodinga-setup" in script
    assert "LicenseFile=LICENSE" in script
    assert 'Name: "english"' in script
    assert 'Name: "korean"' in script

