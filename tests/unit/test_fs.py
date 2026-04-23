from __future__ import annotations

from pathlib import Path

from eodinga.core.fs import absolute_safe, resolve_safe


def test_resolve_safe_normalizes_windows_extended_length_drive_prefix() -> None:
    resolved = resolve_safe(Path(r"\\?\C:\workspace\reports\alpha.txt"))

    assert resolved == Path("C:/workspace/reports/alpha.txt")


def test_absolute_safe_normalizes_windows_extended_length_drive_prefix() -> None:
    absolute = absolute_safe(Path(r"\\?\C:\workspace\reports\alpha.txt"))

    assert absolute == Path("C:/workspace/reports/alpha.txt")
