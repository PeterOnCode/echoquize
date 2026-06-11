"""App version. See specs/002-studio-enhancements/contracts/version.md.

Single source of truth for the version label shown in the UI. Tries the
installed distribution metadata first, then falls back to reading
``[project].version`` from ``pyproject.toml`` (the dependable path today, since
the project has no ``[build-system]`` and is not installed as a distribution).
Never raises — returns ``None`` when the version cannot be determined, so the
header can simply omit it (Constitution Principle VII; FR-026).
"""

import tomllib
from importlib import metadata
from pathlib import Path

# src/version.py -> repo root is two levels up.
_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def app_version() -> str | None:
    """Return the project version (e.g. ``"0.1.0"``), or ``None`` if unknown."""
    try:
        return metadata.version("echoquize")
    except Exception:
        pass  # not installed as a distribution — fall back to the file
    try:
        with open(_PYPROJECT, "rb") as fh:
            data = tomllib.load(fh)
        version = data.get("project", {}).get("version")
        return version if isinstance(version, str) and version else None
    except Exception:
        return None
