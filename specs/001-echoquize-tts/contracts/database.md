# Contract: src/db/database.py

SQLite persistence for Generation Records. (Principle V.) Connection opened with
`check_same_thread=False`; all writes guarded by a module-level `threading.Lock`.

## Functions

```python
def init_db() -> None: ...
    # Creates echoquize.db (at config.DB_PATH) and the generations table + indexes if absent.
    # Idempotent. Runs on import / app startup.

def insert_generation(record: dict) -> str: ...
    # Inserts one row; generates a UUID4 id if absent; returns the id.
    # Required keys: text_input, voice, model, format, speed, file_path, created_at.

def list_generations(limit: int = 50, offset: int = 0, voice: str | None = None) -> list[dict]: ...
    # Returns a page ordered by created_at DESC; optional server-side voice filter (FR-009/D6).

def count_generations(voice: str | None = None) -> int: ...
    # Total rows (for paging controls).

def get_generation(id: str) -> dict | None: ...

def update_tags(id: str, tags: dict) -> None: ...
    # Updates the six tag_* columns for one row (FR-013).

def delete_generation(id: str) -> str | None: ...
    # Deletes one row; returns its file_path so the caller can remove the file. None if not found.

def bulk_delete(
    voice: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[str]: ...
    # Deletes all rows matching the filter; returns their file_paths for backing-file removal (FR-010/D7).
```

## Guarantees

- **Atomic record creation**: a row is inserted only after the file is saved; no orphan rows.
- **Concurrency**: simultaneous writes from multiple tabs do not corrupt the DB (threading lock — FR-024).
- **Pagination**: `list_generations` never loads the whole table; default page size 50 (SC-009).
- **Deletion symmetry**: single and bulk deletes both return file paths so callers remove records
  **and** files (Library `Delete`/`Bulk cleanup` flows call `StorageBackend.delete`).
- File removal is the caller's responsibility (DB layer never touches the storage backend → keeps
  Principle I boundaries clean).

## Contract test (manual)

`init_db()` then `sqlite3 echoquize.db ".schema"` shows the `generations` table; insert a row and
`list_generations(limit=1)` returns it.
