from __future__ import annotations

from pathlib import Path


def test_release_linux_workflow_uses_linux_appimage_dry_run() -> None:
    workflow = Path(".github/workflows/release-linux.yml").read_text(encoding="utf-8")
    assert "python packaging/build.py --target linux-appimage-dry-run" in workflow
    assert "python packaging/build.py --target linux-deb-dry-run" in workflow
    assert "bash packaging/linux/deb.sh" in workflow
