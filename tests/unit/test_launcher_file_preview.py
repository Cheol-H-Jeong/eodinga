from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.launcher_file_preview import filesystem_preview_snippet


def test_filesystem_preview_snippet_reads_utf8_text_when_index_snippet_is_missing(tmp_path: Path) -> None:
    target = tmp_path / "release-notes.txt"
    target.write_text("Alpha release notes\nNext steps\n", encoding="utf-8")

    snippet = filesystem_preview_snippet(
        SearchHit(path=target, parent_path=tmp_path, name=target.name),
    )

    assert snippet == "Alpha release notes Next steps"


def test_filesystem_preview_snippet_skips_binary_content(tmp_path: Path) -> None:
    target = tmp_path / "report.bin"
    target.write_bytes(b"\x00\x01\x02release")

    snippet = filesystem_preview_snippet(
        SearchHit(path=target, parent_path=tmp_path, name=target.name),
    )

    assert snippet is None


def test_filesystem_preview_snippet_preserves_indexed_snippet_priority(tmp_path: Path) -> None:
    target = tmp_path / "release-notes.txt"
    target.write_text("Alpha release notes\n", encoding="utf-8")

    snippet = filesystem_preview_snippet(
        SearchHit(
            path=target,
            parent_path=tmp_path,
            name=target.name,
            snippet="Indexed snippet wins",
        ),
    )

    assert snippet is None
