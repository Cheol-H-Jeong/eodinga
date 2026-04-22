from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest


@pytest.fixture
def tmp_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE files (
          id INTEGER PRIMARY KEY,
          root_id INTEGER NOT NULL,
          path TEXT NOT NULL,
          parent_path TEXT NOT NULL,
          name TEXT NOT NULL,
          name_lower TEXT NOT NULL,
          ext TEXT NOT NULL,
          size INTEGER NOT NULL,
          mtime INTEGER NOT NULL,
          ctime INTEGER NOT NULL,
          is_dir INTEGER NOT NULL,
          is_symlink INTEGER NOT NULL,
          content_hash BLOB,
          indexed_at INTEGER NOT NULL
        );
        CREATE INDEX idx_files_name_lower_prefix ON files(name_lower COLLATE BINARY);
        CREATE INDEX idx_files_ext ON files(ext);
        CREATE INDEX idx_files_mtime ON files(mtime);
        CREATE INDEX idx_files_size ON files(size);
        CREATE INDEX idx_files_parent ON files(parent_path);

        CREATE VIRTUAL TABLE paths_fts USING fts5(
          name, parent_path, path,
          tokenize="unicode61 remove_diacritics 2 tokenchars '._-/'"
        );

        CREATE VIRTUAL TABLE content_fts USING fts5(
          title, head_text, body_text,
          tokenize="unicode61 remove_diacritics 2 tokenchars '._-'"
        );

        CREATE TABLE content_map (
          file_id INTEGER PRIMARY KEY,
          fts_rowid INTEGER NOT NULL UNIQUE,
          parser TEXT NOT NULL,
          parsed_at INTEGER NOT NULL,
          content_sha BLOB NOT NULL
        );
        """
    )
    yield conn
    conn.close()
