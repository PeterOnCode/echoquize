# Contract: Database (`src/db/database.py`, delta)

Extends the feature-001 `generations` table and CRUD for expanded tag persistence (US2) and Library
rename (US5). The database remains the **source of truth** for tags. All access stays behind the
module-level threading lock (Principle V).

## Schema delta

Two additive columns: `tag_track TEXT`, `tags_extra TEXT` (JSON). `tag_year` is reused as the
recording date/time (no rename). See [data-model.md](../data-model.md) for the JSON shape.

## Migration — `init_db()` (delta)

After the existing `CREATE TABLE IF NOT EXISTS`:

```text
existing = {row["name"] for row in conn.execute("PRAGMA table_info(generations)")}
for col in ("tag_track", "tags_extra"):
    if col not in existing:
        conn.execute(f"ALTER TABLE generations ADD COLUMN {col} TEXT")
```

Idempotent and additive; existing rows get `NULL`. No data loss, no backfill (Principle V).

## `insert_generation(record)` (delta)

`_COLUMNS` gains `tag_track`, `tags_extra`. `record` may include:

- `tag_track`: str | None
- `tags_extra`: a dict (serialized to JSON) or a pre-serialized JSON str or None. Empty → stored as
  `NULL` (not `"{}"`).

All existing keys behave as before; `tag_year` now carries a recording-date string.

## `update_tags(gid, tags, file_size=None)` (delta)

Replaces the full expanded tag set on a record:

- writes `tag_title/artist/album/comment/genre`, `tag_year` (from `date`/`year`), `tag_track`, and
  `tags_extra` (JSON of `languages`/`custom_text`/`custom_url`; `NULL` when all empty);
- empty/missing values are stored as `NULL` so the row stays in sync with a cleared file;
- optional `file_size` update unchanged.

## `update_file_path(gid, new_path, file_size=None)` (NEW)

Update a record's `file_path` (and optionally `file_size`) after a storage `rename()` (US5).

```python
def update_file_path(gid: str, new_path: str, file_size: int | None = None) -> None
```

- Used by the Library "edit details" save when the filename stem changed.
- Leaves tags untouched (tags are updated separately by `update_tags`).

## Reads (`get_generation`, `list_generations`, `bulk_delete`, …)

Return the new columns alongside existing ones (they already `SELECT *`). `tags_extra` is returned
as its stored JSON string; the UI/editor parses it. No query/index changes.

**Guarantees**:

- Migration leaves every existing row intact and the app fully functional on an old database file.
- A record always references the real on-disk path (insert / rename keep `file_path` truthful), so
  preview/download/delete/tag-edit resolve correctly (FR-019, FR-041).
