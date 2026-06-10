"""Storage backend abstraction. See contracts/storage-backend.md.

Callers depend only on this ABC — never on a concrete backend or on
filesystem paths (Constitution Principle I).
"""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract place that audio bytes are persisted to and read back from."""

    @abstractmethod
    def save(self, data: bytes, filename: str) -> str:
        """Persist ``data`` under ``filename``; return the backend path/key."""

    @abstractmethod
    def rename(self, old_path: str, new_filename: str) -> str:
        """Move the object at ``old_path`` to ``new_filename`` within its current
        folder, collision-safe; return the new backend path/key (US5)."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Remove the object at ``path``. A missing object is tolerated."""

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Return a locator for playback/download (local: the filesystem path)."""
