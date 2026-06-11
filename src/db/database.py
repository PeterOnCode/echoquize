"""SQLite persistence for generation records. See contracts/database.md.

Opened with ``check_same_thread=False`` and guarded by a module-level lock so
concurrent generations from multiple browser tabs cannot corrupt the DB
(Constitution Principle V). US1 implements the create/read functions; the
library list/delete/bulk functions are added in US2.
"""

import json
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
  tag_year    TEXT,
  tag_track   TEXT,
  tags_extra  TEXT
);
CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_voice ON generations(voice);
"""

_COLUMNS = (
    "id", "text_input", "voice", "model", "format", "speed", "file_path",
    "file_size", "created_at", "tag_title", "tag_artist", "tag_album",
    "tag_comment", "tag_genre", "tag_year", "tag_track", "tags_extra",
)

_NEW_COLUMNS = ("tag_track", "tags_extra")  # added in feature 002 (migration)


def _coerce_extra(value) -> str | None:
    """Accept a dict, a pre-serialized JSON string, or None → JSON string or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False) if value else None
    return None


def _build_extra(tags: dict) -> str | None:
    """Build the ``tags_extra`` JSON (languages/custom_text/custom_url) or None."""
    tags = tags or {}
    langs = tags.get("languages") or []
    if isinstance(langs, str):
        langs = [langs]
    langs = [str(x).strip() for x in langs if str(x).strip()]

    def _pairs(items, out_key):
        # Canonical shape (per data-model): custom_text uses "value", custom_url uses "url".
        out = []
        for item in items or []:
            if isinstance(item, dict):
                desc = str(item.get("desc") or "").strip()
                val = str(item.get(out_key) or item.get("value") or "").strip()
                if val:
                    out.append({"desc": desc, out_key: val})
        return out

    extra: dict = {}
    if langs:
        extra["languages"] = langs
    custom_text = _pairs(tags.get("custom_text"), "value")
    if custom_text:
        extra["custom_text"] = custom_text
    custom_url = _pairs(tags.get("custom_url"), "url")
    if custom_url:
        extra["custom_url"] = custom_url
    return json.dumps(extra, ensure_ascii=False) if extra else None


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
        # Additive migration for pre-002 databases: add any missing new columns.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(generations)")}
        for col in _NEW_COLUMNS:
            if col not in existing:
                conn.execute(f"ALTER TABLE generations ADD COLUMN {col} TEXT")
        conn.commit()


def insert_generation(record: dict) -> str:
    """Insert one generation row; return its id (generated if absent)."""
    gid = record.get("id") or str(uuid.uuid4())
    # Store tz-naive UTC: the bulk_delete date filters compare created_at
    # lexicographically against UI cutoffs that carry no offset, so a trailing
    # "+00:00" would mis-sort boundary rows. We always compute in UTC.
    created = record.get("created_at") or datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
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
        record.get("tag_track"),
        _coerce_extra(record.get("tags_extra")),
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


def update_tags(gid: str, tags: dict, file_size: int | None = None) -> None:
    """Replace the tag columns for one generation — the full expanded set (FR-037).

    Accepts the expanded logical tag dict; the legacy 6-key shape (``year``) is
    still honored. Missing/empty values are stored as NULL so the record stays in
    sync with a cleared file. When ``file_size`` is given, it is updated too.
    """
    tags = tags or {}

    def _val(key: str) -> str | None:
        return str(tags.get(key) or "").strip() or None

    date_val = _val("date") or _val("year")  # ``date`` generalizes the old ``year``

    cols = [
        "tag_title = ?", "tag_artist = ?", "tag_album = ?",
        "tag_comment = ?", "tag_genre = ?", "tag_year = ?",
        "tag_track = ?", "tags_extra = ?",
    ]
    params: list = [
        _val("title"), _val("artist"), _val("album"),
        _val("comment"), _val("genre"), date_val,
        _val("track"), _build_extra(tags),
    ]
    if file_size is not None:
        cols.append("file_size = ?")
        params.append(int(file_size))
    params.append(gid)

    with _lock:
        conn = _get_conn()
        conn.execute(f"UPDATE generations SET {', '.join(cols)} WHERE id = ?", params)
        conn.commit()


def update_file_path(gid: str, new_path: str, file_size: int | None = None) -> None:
    """Update a record's stored ``file_path`` after a storage rename (US5).

    Leaves tags untouched; optionally updates ``file_size``.
    """
    cols = ["file_path = ?"]
    params: list = [new_path]
    if file_size is not None:
        cols.append("file_size = ?")
        params.append(int(file_size))
    params.append(gid)
    with _lock:
        conn = _get_conn()
        conn.execute(f"UPDATE generations SET {', '.join(cols)} WHERE id = ?", params)
        conn.commit()


def list_generations(
    limit: int = 50, offset: int = 0, voice: str | None = None
) -> list[dict]:
    """Return a page of generations, newest first, optionally filtered by voice."""
    query = "SELECT * FROM generations"
    params: list = []
    if voice:
        query += " WHERE voice = ?"
        params.append(voice)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    with _lock:
        rows = _get_conn().execute(query, params).fetchall()
    return [dict(r) for r in rows]


def count_generations(voice: str | None = None) -> int:
    """Total number of generations (optionally filtered by voice)."""
    query = "SELECT COUNT(*) AS n FROM generations"
    params: list = []
    if voice:
        query += " WHERE voice = ?"
        params.append(voice)
    with _lock:
        return _get_conn().execute(query, params).fetchone()["n"]


def delete_generation(gid: str) -> str | None:
    """Delete one row; return its file_path so the caller can remove the file."""
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT file_path FROM generations WHERE id = ?", (gid,)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM generations WHERE id = ?", (gid,))
        conn.commit()
    return row["file_path"]


def bulk_delete(
    voice: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[str]:
    """Delete all rows matching the filter; return their file_paths.

    ``date_from``/``date_to`` are ISO-8601 strings compared against ``created_at``
    (which sorts lexicographically). With no filter, deletes everything — callers
    must require explicit confirmation.
    """
    clauses: list[str] = []
    params: list = []
    if voice:
        clauses.append("voice = ?")
        params.append(voice)
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lock:
        conn = _get_conn()
        paths = [
            r["file_path"]
            for r in conn.execute(
                f"SELECT file_path FROM generations{where}", params
            ).fetchall()
        ]
        conn.execute(f"DELETE FROM generations{where}", params)
        conn.commit()
    return paths
