"""Local filesystem storage backend. See contracts/storage-backend.md."""

import os
from datetime import datetime, timezone
from pathlib import Path

import config
from src.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Stores files under ``AUDIO_DIR/YYYY/MM/``."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or config.AUDIO_DIR)

    def save(self, data: bytes, filename: str) -> str:
        now = datetime.now(timezone.utc)
        subdir = self.base_dir / f"{now:%Y}" / f"{now:%m}"
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / filename
        path.write_bytes(data)
        return str(path)

    def delete(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # tolerant: file may already be gone

    def get_url(self, path: str) -> str:
        return path
