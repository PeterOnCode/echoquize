"""Storage factory. See contracts/storage-backend.md.

``get_storage()`` returns the backend selected by ``STORAGE_BACKEND``. The
``s3``/``gdrive`` backends are imported lazily so the package stays importable
before those stubs exist.
"""

import config
from src.storage.base import StorageBackend
from src.storage.local import LocalStorage

__all__ = ["StorageBackend", "LocalStorage", "get_storage"]


def get_storage() -> StorageBackend:
    backend = (config.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        return LocalStorage()
    if backend == "s3":
        from src.storage.s3 import S3Storage

        return S3Storage()
    if backend == "gdrive":
        from src.storage.gdrive import GDriveStorage

        return GDriveStorage()
    raise ValueError(
        f"Unknown STORAGE_BACKEND {backend!r}. Expected one of: local, s3, gdrive."
    )
