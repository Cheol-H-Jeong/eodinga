from __future__ import annotations

from pathlib import Path

import pytest

from eodinga.common import SearchHit
import eodinga.gui.launcher_file_preview as preview_module
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


def test_filesystem_preview_snippet_uses_readonly_fs_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "release-notes.txt"
    target.write_text("Alpha release notes\n", encoding="utf-8")
    calls: list[tuple[Path, str]] = []
    original_open_readonly = preview_module.open_readonly

    def recording_open_readonly(path: Path, mode: str = "rb", encoding: str | None = None):
        calls.append((path, mode))
        return original_open_readonly(path, mode=mode, encoding=encoding)

    monkeypatch.setattr(preview_module, "open_readonly", recording_open_readonly)

    snippet = filesystem_preview_snippet(
        SearchHit(path=target, parent_path=tmp_path, name=target.name),
    )

    assert snippet == "Alpha release notes"
    assert calls == [(target, "rb")]
