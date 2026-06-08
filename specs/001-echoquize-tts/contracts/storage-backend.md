# Contract: src/storage/ (StorageBackend + factory)

The mandated abstraction (Constitution Principle I). Callers depend ONLY on this interface, never on
a concrete backend or on filesystem paths.

## ABC: `StorageBackend` (`src/storage/base.py`)

```python
class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, filename: str) -> str: ...   # returns backend path/key
    @abstractmethod
    def delete(self, path: str) -> None: ...
    @abstractmethod
    def get_url(self, path: str) -> str: ...                 # local: filesystem path
```

## Factory: `get_storage()` (`src/storage/__init__.py`)

```python
def get_storage() -> StorageBackend: ...
```

- Reads `config.STORAGE_BACKEND`: `local` (default) → `LocalStorage`; `s3` → `S3Storage`;
  `gdrive` → `GDriveStorage`.
- Unknown value → `ValueError` (FR-021 / research D8).

## `LocalStorage` (`src/storage/local.py`)

- `save(data, filename)` writes under `AUDIO_DIR/YYYY/MM/`, creating dirs as needed; returns the path.
- `delete(path)` removes the file; a missing file is tolerated (no raise — readiness CHK015).
- `get_url(path)` returns the filesystem path (for `gr.Audio`/`gr.File`).

## Stubs

- `S3Storage` — constructor reads `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`; methods raise `NotImplementedError` with a clear message if not wired /
  boto3 absent (boto3 is an optional `s3` extra).
- `GDriveStorage` — constructor reads `GDRIVE_FOLDER_ID`, `GDRIVE_CREDENTIALS_JSON`; methods raise
  `NotImplementedError("Google Drive storage not yet implemented")`. Import MUST NOT crash without
  google libraries installed.

## Guarantee (SC-007)

Switching `STORAGE_BACKEND` requires no change to TTS, UI, or DB code; the user-facing generate/browse
experience is unchanged for any working backend.

## Contract tests (manual)

- `get_storage()` with unset/`local` → `LocalStorage`; with bogus value → `ValueError`.
- `LocalStorage().save(b"test", "test.mp3")` → creates file, returns its path.
