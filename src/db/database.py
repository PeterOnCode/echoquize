"""SQLite persistence for generation records. See contracts/database.md.

Opened with ``check_same_thread=False`` and guarded by a module-level lock so
concurrent generations from multiple browser tabs cannot corrupt the DB
(Constitution Principle V). US1 implements the create/read functions; the
library list/delete/bulk functions are added in US2.
"""

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
  id          TEXT PRIMARY KEY,
  text_input  TEXT NOT NULL,
  voice       TEXT NOT NULL,
  model       TEXT NOT NULL,
  format      TEXT NOT NULL,
  speed       REAL NOT NULL,
  file_path   TEXT NOT NULL,
  file_size   INTEGER,
  created_at  TEXT NOT NULL,
  tag_title   TEXT,
  tag_artist  TEXT,
  tag_album   TEXT,
  tag_comment TEXT,
  tag_genre   TEXT,
  tag_year    TEXT
);
CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_voice ON generations(voice);
"""

_COLUMNS = (
    "id", "text_input", "voice", "model", "format", "speed", "file_path",
    "file_size", "created_at", "tag_title", "tag_artist", "tag_album",
    "tag_comment", "tag_genre", "tag_year",
)


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        parent = os.path.dirname(os.path.abspath(config.DB_PATH))
        os.makedirs(parent, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db() -> None:
    """Create the database file and schema if they do not exist (idempotent)."""
    with _lock:
        conn = _get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()


def insert_generation(record: dict) -> str:
    """Insert one generation row; return its id (generated if absent)."""
    gid = record.get("id") or str(uuid.uuid4())
    created = record.get("created_at") or datetime.now(timezone.utc).isoformat()
    values = (
        gid,
        record["text_input"],
        record["voice"],
        record["model"],
        record["format"],
        float(record["speed"]),
        record["file_path"],
        record.get("file_size"),
        created,
        record.get("tag_title"),
        record.get("tag_artist"),
        record.get("tag_album"),
        record.get("tag_comment"),
        record.get("tag_genre"),
        record.get("tag_year"),
    )
    placeholders = ", ".join("?" for _ in _COLUMNS)
    with _lock:
        conn = _get_conn()
        conn.execute(
            f"INSERT INTO generations ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    return gid


def get_generation(gid: str) -> dict | None:
    """Return one generation row as a dict, or None if not found."""
    with _lock:
        cur = _get_conn().execute("SELECT * FROM generations WHERE id = ?", (gid,))
        row = cur.fetchone()
    return dict(row) if row else None
