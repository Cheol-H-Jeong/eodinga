from __future__ import annotations

import sqlite3

PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA mmap_size=1073741824;",
    "PRAGMA temp_store=MEMORY;",
    "PRAGMA cache_size=-64000;",
    "PRAGMA foreign_keys=ON;",
)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS roots (
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  include TEXT,
  exclude TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  added_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY,
  root_id INTEGER NOT NULL REFERENCES roots(id),
  path TEXT NOT NULL,
  parent_path TEXT NOT NULL,
  name TEXT NOT NULL,
  name_lower TEXT NOT NULL,
  ext TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime INTEGER NOT NULL,
  ctime INTEGER NOT NULL,
  is_dir INTEGER NOT NULL CHECK (is_dir IN (0,1)),
  is_symlink INTEGER NOT NULL CHECK (is_symlink IN (0,1)),
  content_hash BLOB,
  indexed_at INTEGER NOT NULL,
  UNIQUE(path)
);
CREATE INDEX IF NOT EXISTS idx_files_name_lower_prefix ON files(name_lower COLLATE BINARY);
CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
CREATE INDEX IF NOT EXISTS idx_files_size ON files(size);
CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent_path);

CREATE VIRTUAL TABLE IF NOT EXISTS paths_fts USING fts5(
  name, parent_path, path,
  content='files', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2 tokenchars '._-/'"
);

CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
  title, head_text, body_text,
  tokenize="unicode61 remove_diacritics 2 tokenchars '._-'"
);

CREATE TABLE IF NOT EXISTS content_map (
  file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  fts_rowid INTEGER NOT NULL UNIQUE,
  parser TEXT NOT NULL,
  parsed_at INTEGER NOT NULL,
  content_sha BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
  INSERT INTO paths_fts(rowid, name, parent_path, path)
  VALUES (new.id, new.name, new.parent_path, new.path);
END;

CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
  INSERT INTO paths_fts(paths_fts, rowid, name, parent_path, path)
  VALUES('delete', old.id, old.name, old.parent_path, old.path);
END;

CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
  INSERT INTO paths_fts(paths_fts, rowid, name, parent_path, path)
  VALUES('delete', old.id, old.name, old.parent_path, old.path);
  INSERT INTO paths_fts(rowid, name, parent_path, path)
  VALUES (new.id, new.name, new.parent_path, new.path);
END;
"""


def apply_schema(conn: sqlite3.Connection) -> None:
    for pragma in PRAGMAS:
        conn.execute(pragma)
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def current_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0
