"""Format-aware metadata tag writer using mutagen. See contracts/tag-writer.md.

Writing replaces the full tag set on every call, so the same function both edits
and clears tags and stays idempotent. MP3/WAV are written as ID3 **v2.4.0**
explicitly. PCM/raw-AAC have no usable container and raise
``TagsNotSupportedError`` — callers surface a notice and still complete the
generation (Principle VII).

Logical tag set (all optional; missing/empty clears that frame):
  title, artist, album, comment, genre, date (legacy ``year`` accepted),
  track, languages: [str], custom_text: [{desc, value}], custom_url: [{desc, url}]
"""

import re

from mutagen.flac import FLAC
from mutagen.id3 import (
    COMM,
    ID3,
    ID3NoHeaderError,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TLAN,
    TPE1,
    TRCK,
    TXXX,
    WXXX,
)
from mutagen.oggopus import OggOpus
from mutagen.wave import WAVE

# Logical single-value key -> Vorbis comment field (flac/opus). Uppercase per
# Vorbis convention. ``date`` carries the recording date/time (TDRC).
_VORBIS_KEYS = {
    "title": "TITLE", "artist": "ARTIST", "album": "ALBUM",
    "comment": "COMMENT", "genre": "GENRE", "date": "DATE", "track": "TRACKNUMBER",
}

_SIMPLE_KEYS = ("title", "artist", "album", "comment", "genre", "date", "track")
_VORBIS_FIELD_RE = re.compile(r"[^A-Z0-9_]")


class TagsNotSupportedError(ValueError):
    """Raised when the format has no container that can carry tags (pcm, raw aac)."""


def _clean_pairs(items, value_key: str) -> list[dict]:
    """Normalize custom text/URL entries to ``[{"desc", "value"}]`` (value required)."""
    cleaned: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("desc") or "").strip()
        value = str(item.get(value_key) or item.get("value") or "").strip()
        if value:
            cleaned.append({"desc": desc, "value": value})
    return cleaned


def _normalize(tags: dict) -> dict:
    """Canonical expanded tag dict; accepts the legacy 6-key shape (``year``)."""
    tags = tags or {}
    out = {k: str(tags.get(k) or "").strip() for k in _SIMPLE_KEYS}
    # ``date`` generalizes the old ``year`` field.
    if not out["date"]:
        out["date"] = str(tags.get("year") or "").strip()
    langs = tags.get("languages") or []
    if isinstance(langs, str):
        langs = [langs]
    out["languages"] = [str(x).strip() for x in langs if str(x).strip()]
    out["custom_text"] = _clean_pairs(tags.get("custom_text"), "value")
    out["custom_url"] = _clean_pairs(tags.get("custom_url"), "url")
    return out


def write_tags(file_path: str, fmt: str, tags: dict) -> None:
    """Write ``tags`` into ``file_path`` for ``fmt``; replaces the existing set.

    Raises ``TagsNotSupportedError`` for pcm and raw aac (ADTS, not M4A).
    """
    fmt = (fmt or "").lower()
    if fmt == "pcm":
        raise TagsNotSupportedError("Tags are not supported for PCM format.")
    if fmt == "aac":
        raise TagsNotSupportedError("Tags are not supported for raw AAC (ADTS) files.")

    t = _normalize(tags)
    if fmt == "mp3":
        _write_mp3(file_path, t)
    elif fmt == "wav":
        _write_wav(file_path, t)
    elif fmt in ("flac", "opus"):
        _write_vorbis(file_path, fmt, t)
    else:
        raise TagsNotSupportedError(f"Tags are not supported for {fmt!r}.")


def _apply_id3(id3: ID3, t: dict) -> None:
    """Replace the managed frames on an ID3 tag block (mp3 + wav share this)."""
    for frame_id in ("TIT2", "TPE1", "TALB", "TCON", "TDRC", "TRCK", "TLAN",
                     "COMM", "TXXX", "WXXX"):
        id3.delall(frame_id)
    if t["title"]:
        id3.add(TIT2(encoding=3, text=[t["title"]]))
    if t["artist"]:
        id3.add(TPE1(encoding=3, text=[t["artist"]]))
    if t["album"]:
        id3.add(TALB(encoding=3, text=[t["album"]]))
    if t["genre"]:
        id3.add(TCON(encoding=3, text=[t["genre"]]))
    if t["date"]:
        id3.add(TDRC(encoding=3, text=[t["date"]]))
    if t["track"]:
        id3.add(TRCK(encoding=3, text=[t["track"]]))
    if t["comment"]:
        id3.add(COMM(encoding=3, lang="eng", desc="", text=[t["comment"]]))
    if t["languages"]:
        id3.add(TLAN(encoding=3, text=t["languages"]))
    for pair in t["custom_text"]:
        id3.add(TXXX(encoding=3, desc=pair["desc"], text=[pair["value"]]))
    for pair in t["custom_url"]:
        id3.add(WXXX(encoding=3, desc=pair["desc"], url=pair["value"]))


def _write_mp3(path: str, t: dict) -> None:
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()  # fresh tags; .save(path) writes the header (research D9)
    _apply_id3(id3, t)
    id3.save(path, v2_version=4)  # ID3v2.4.0 explicitly (FR-033)


def _write_wav(path: str, t: dict) -> None:
    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    _apply_id3(audio.tags, t)
    audio.save(v2_version=4)


def _vorbis_field(desc: str) -> str:
    """Sanitize a custom-text description into a Vorbis field name (A-Z0-9_)."""
    return _VORBIS_FIELD_RE.sub("", desc.upper())


def _write_vorbis(path: str, fmt: str, t: dict) -> None:
    audio = FLAC(path) if fmt == "flac" else OggOpus(path)
    if audio.tags is None:  # rare: a container with no comment block yet
        audio.add_tags()
    tags = audio.tags
    tags.clear()  # full replace; this app is the sole writer of these files
    for key, field in _VORBIS_KEYS.items():
        if t[key]:
            tags[field] = [t[key]]
    if t["languages"]:
        tags["LANGUAGE"] = t["languages"]
    for pair in t["custom_text"]:
        field = _vorbis_field(pair["desc"])
        if field:
            tags[field] = [pair["value"]]
    # custom_url (WXXX) has no clean Vorbis equivalent — skipped; caller notes it.
    audio.save()
