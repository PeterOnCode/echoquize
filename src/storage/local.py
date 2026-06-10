"""Local filesystem storage backend. See contracts/storage-backend.md."""

import os
from datetime import datetime, timezone
from pathlib import Path

import config
from src.storage.base import StorageBackend

_MAX_STEM = 64  # filename stem cap (matches the slug rule in src/naming.py)


class LocalStorage(StorageBackend):
    """Stores files under ``AUDIO_DIR/YYYY/MM/DD/`` (UTC)."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or config.AUDIO_DIR)

    def save(self, data: bytes, filename: str) -> str:
        now = datetime.now(timezone.utc)
        subdir = self.base_dir / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
        subdir.mkdir(parents=True, exist_ok=True)
        path = self._unique_path(subdir, filename)
        path.write_bytes(data)
        return str(path)

    @staticmethod
    def _unique_path(subdir: Path, filename: str) -> Path:
        """Return a non-colliding path in ``subdir``; on collision, suffix the stem
        (``_2``, ``_3``, …) while keeping the whole stem within the 64-char cap.
        Never overwrites an existing file (FR-017)."""
        stem, ext = os.path.splitext(filename)
        candidate = subdir / filename
        n = 2
        while candidate.exists():
            suffix = f"_{n}"
            base = stem[: max(1, _MAX_STEM - len(suffix))]
            candidate = subdir / f"{base}{suffix}{ext}"
            n += 1
        return candidate

    def delete(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # tolerant: file may already be gone

    def get_url(self, path: str) -> str:
        return path
