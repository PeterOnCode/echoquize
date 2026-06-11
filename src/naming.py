"""Filename slug helper. See specs/002-studio-enhancements/contracts/naming.md.

Pure: no I/O, no config, no storage knowledge. Turns a title into a
filesystem-safe stem (no extension). Returns ``""`` when the title has no
ASCII-representable alphanumerics (e.g. a non-Latin script) — callers fall
back to a UUID stem. Uniqueness/``_2`` suffixing is the storage backend's job,
not this module's (Constitution Principle I).
"""

import re
import unicodedata

MAX_STEM = 64

_WHITESPACE = re.compile(r"\s+")
_DISALLOWED = re.compile(r"[^a-z0-9_-]")
_SEPARATOR_RUN = re.compile(r"[_-]{2,}")


def slugify(title: str) -> str:
    """Return a ``<= MAX_STEM``-char filename stem derived from ``title``.

    Steps (per contract): transliterate accented/Latin characters to ASCII,
    lowercase, whitespace runs -> ``_``, drop anything outside ``[a-z0-9_-]``,
    collapse/trim separator runs, cap at 64 chars. Never raises; may return
    ``""`` when nothing usable remains.
    """
    # 1. Transliterate to ASCII (é→e, ñ→n); non-Latin scripts drop to empty.
    ascii_text = (
        unicodedata.normalize("NFKD", title or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    # 2. lowercase  3. whitespace runs -> single underscore
    stem = _WHITESPACE.sub("_", ascii_text.lower())
    # 4. drop every character outside [a-z0-9_-]
    stem = _DISALLOWED.sub("", stem)
    # 5. collapse separator runs to one underscore; trim leading/trailing seps
    stem = _SEPARATOR_RUN.sub("_", stem).strip("_-")
    # 6. cap length; a cut that lands on a separator is trimmed off again
    return stem[:MAX_STEM].strip("_-")
