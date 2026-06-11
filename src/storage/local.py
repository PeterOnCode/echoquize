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
    def _unique_path(subdir: Path, filename: str, ignore: Path | None = None) -> Path:
        """Return a non-colliding path in ``subdir``; on collision, suffix the stem
        (``_2``, ``_3``, …) while keeping the whole stem within the 64-char cap.
        Never overwrites an existing file (FR-017). ``ignore`` (a rename's own
        source) is not counted as a collision, so a file is never suffixed past
        itself when its requested name is taken by a different file."""
        stem, ext = os.path.splitext(filename)
        candidate = subdir / filename
        n = 2
        while candidate.exists() and candidate != ignore:
            suffix = f"_{n}"
            base = stem[: max(1, _MAX_STEM - len(suffix))]
            candidate = subdir / f"{base}{suffix}{ext}"
            n += 1
        return candidate

    def rename(self, old_path: str, new_filename: str) -> str:
        """Move ``old_path`` to ``new_filename`` within its folder, collision-safe.

        A no-op when the name is unchanged. Raises ``FileNotFoundError`` when the
        source is missing so the caller can surface a friendly message (US5)."""
        src = Path(old_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {old_path}")
        if (src.parent / new_filename) == src:
            return old_path  # unchanged
        dest = self._unique_path(src.parent, new_filename, ignore=src)
        if dest == src:
            return old_path  # only free slot is the file's own name — nothing to move
        os.replace(src, dest)  # move within the same dated folder
        return str(dest)

    def delete(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # tolerant: file may already be gone

    def get_url(self, path: str) -> str:
        return path
