"""S3 storage backend — ready-to-wire stub. See contracts/storage-backend.md.

Reads its configuration from the environment so the backend can be selected
purely via ``STORAGE_BACKEND=s3`` (Constitution Principle I/III). ``boto3`` is an
optional dependency (the ``s3`` extra): importing this module MUST NOT fail when
boto3 is absent — only an actual operation surfaces a clear error.
"""

import os

from src.storage.base import StorageBackend

try:  # boto3 is optional (install via `uv sync --extra s3`)
    import boto3  # noqa: F401

    _BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the s3 extra
    _BOTO3_AVAILABLE = False

_NOT_IMPLEMENTED = (
    "S3 storage is not yet implemented. Set STORAGE_BACKEND=local, or finish "
    "wiring src/storage/s3.py (install the boto3 extra with `uv sync --extra s3`)."
)


class S3Storage(StorageBackend):
    """Stub for S3-compatible object storage (AWS S3, MinIO, Cloudflare R2).

    When implemented, objects use the same dated key convention as local storage —
    ``YYYY/MM/DD/<filename>`` (UTC), collision-safe within the day folder.
    """

    def __init__(self) -> None:
        self.bucket = os.environ.get("S3_BUCKET")
        self.endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        self.access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.boto3_available = _BOTO3_AVAILABLE

    def save(self, data: bytes, filename: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def rename(self, old_path: str, new_filename: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def delete(self, path: str) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_url(self, path: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)
