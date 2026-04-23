from __future__ import annotations

from eodinga.query.path_norm import strip_windows_extended_prefix, windows_path_variants


def test_strip_windows_extended_prefix_normalizes_drive_and_unc_forms() -> None:
    assert strip_windows_extended_prefix(r"\\?\C:\workspace\reports") == r"C:\workspace\reports"
    assert strip_windows_extended_prefix(r"\\?\UNC\server\share\reports") == r"\\server\share\reports"


def test_windows_path_variants_preserve_deterministic_drive_order() -> None:
    assert windows_path_variants(r"\\?\C:\workspace\reports") == (
        r"C:\workspace\reports",
        "C:/workspace/reports",
        r"c:\workspace\reports",
        "c:/workspace/reports",
    )


def test_windows_path_variants_preserve_unc_forms_without_duplicates() -> None:
    assert windows_path_variants(r"\\?\UNC\server\share\reports") == (
        r"\\server\share\reports",
        "//server/share/reports",
    )
