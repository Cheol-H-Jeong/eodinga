from __future__ import annotations

from pathlib import Path

from eodinga.common import SearchHit
from eodinga.gui.launcher_file_preview import filesystem_preview, filesystem_preview_metadata, filesystem_preview_snippet


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


def test_filesystem_preview_metadata_formats_regular_files(tmp_path: Path) -> None:
    target = tmp_path / "release-notes.txt"
    target.write_text("Alpha release notes\n", encoding="utf-8")

    metadata = filesystem_preview_metadata(target)

    assert metadata is not None
    assert metadata.startswith("File · ")
    assert "modified " in metadata


def test_filesystem_preview_metadata_formats_directories(tmp_path: Path) -> None:
    metadata = filesystem_preview_metadata(tmp_path)

    assert metadata is not None
    assert metadata.startswith("Directory · modified ")


def test_filesystem_preview_returns_snippet_and_metadata(tmp_path: Path) -> None:
    target = tmp_path / "release-notes.txt"
    target.write_text("Alpha release notes\nNext steps\n", encoding="utf-8")

    preview = filesystem_preview(SearchHit(path=target, parent_path=tmp_path, name=target.name))

    assert preview is not None
    assert preview.snippet == "Alpha release notes Next steps"
    assert preview.metadata is not None
