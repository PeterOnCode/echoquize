"""Google Drive storage backend — ready-to-wire stub. See contracts/storage-backend.md.

Reads its configuration from the environment so the backend can be selected
purely via ``STORAGE_BACKEND=gdrive`` (Constitution Principle I/III). The Google
client libraries are NOT a declared dependency: importing this module MUST stay
safe without them — only an actual operation surfaces a clear error.
"""

import os

from src.storage.base import StorageBackend

_NOT_IMPLEMENTED = "Google Drive storage not yet implemented"


class GDriveStorage(StorageBackend):
    """Stub for Google Drive storage.

    When implemented, files use the same dated layout as local storage —
    ``YYYY/MM/DD`` folders (UTC), collision-safe within the day folder.
    """

    def __init__(self) -> None:
        self.folder_id = os.environ.get("GDRIVE_FOLDER_ID")
        self.credentials_json = os.environ.get("GDRIVE_CREDENTIALS_JSON")

    def save(self, data: bytes, filename: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def delete(self, path: str) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_url(self, path: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)
