"""Configuration loaded from environment (.env). See contracts/config.md.

Reads every runtime knob from the environment (12-factor) and fails fast at
import time when a required value is missing.
"""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

_ENV_FILE = Path(__file__).resolve().with_name(".env")

load_dotenv(dotenv_path=_ENV_FILE)
_DOTENV_VALUES = dotenv_values(_ENV_FILE) if _ENV_FILE.exists() else {}


def _get_env(
    name: str, default: str | None = None, *, dotenv_overrides: bool = False
) -> str | None:
    env_value = os.environ.get(name)
    dotenv_value = _DOTENV_VALUES.get(name)

    if dotenv_overrides and dotenv_value and dotenv_value.strip():
        value = dotenv_value
    else:
        value = env_value
        if value is None or not value.strip():
            value = dotenv_value

    if value is None:
        value = default
    return value.strip() if value is not None else None


OPENAI_API_KEY = _get_env("OPENAI_API_KEY", "", dotenv_overrides=True)
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is not set. Add it to your .env file or the environment."
    )
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

AUDIO_DIR = _get_env("AUDIO_DIR", "./audio")
DB_PATH = _get_env("DB_PATH", "./echoquize.db")

HOST = _get_env("HOST", "0.0.0.0")
try:
    PORT = int(_get_env("PORT", "7860"))
except ValueError as exc:  # pragma: no cover - config error path
    raise ValueError(f"PORT must be an integer, got {_get_env('PORT')!r}") from exc

STORAGE_BACKEND = _get_env("STORAGE_BACKEND", "local")

UI_USERNAME = _get_env("UI_USERNAME") or None
UI_PASSWORD = _get_env("UI_PASSWORD") or None


def _default_tags() -> dict:
    """Optional default tag values (US7); only keys whose env var is set appear.

    Pre-fills the Generate form and seeds new queue items. ``title`` is never
    defaulted (it is per-clip and drives the filename). Never raises — a
    missing/blank value simply contributes no key (FR-048).
    """
    pairs = {
        "artist": _get_env("DEFAULT_TAG_ARTIST"),
        "album": _get_env("DEFAULT_TAG_ALBUM"),
        "genre": _get_env("DEFAULT_TAG_GENRE"),
        "comment": _get_env("DEFAULT_TAG_COMMENT"),
        "languages": _get_env("DEFAULT_TAG_LANGUAGE"),
    }
    return {k: v for k, v in pairs.items() if v}


DEFAULT_TAGS = _default_tags()
