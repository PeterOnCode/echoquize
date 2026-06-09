"""Format-aware metadata tag writer using mutagen. See contracts/tag-writer.md.

Writing replaces the full tag set on every call (per-key set or delete), so the
same function both edits and clears tags and stays idempotent. PCM/AAC have no
usable container and raise ``TagsNotSupportedError`` — callers surface a notice
and still complete the generation (FR-014, Principle VII).
"""

from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import (
    COMM,
    ID3NoHeaderError,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
)
from mutagen.oggopus import OggOpus
from mutagen.wave import WAVE

TAG_KEYS = ("title", "artist", "album", "comment", "genre", "year")

# Logical key -> EasyID3 key (mp3). `year` is ID3 `date`; `comment` is registered below.
_EASYID3_KEYS = {
    "title": "title", "artist": "artist", "album": "album",
    "comment": "comment", "genre": "genre", "year": "date",
}
# Logical key -> Vorbis comment field (flac, opus). Uppercase per Vorbis convention
# (field names are case-insensitive). COMMENT is the field players surface as "Comment".
_VORBIS_KEYS = {
    "title": "TITLE", "artist": "ARTIST", "album": "ALBUM",
    "comment": "COMMENT", "genre": "GENRE", "year": "DATE",
}
# Logical key -> ID3 frame class for the WAV path (comment handled separately as COMM).
_WAV_FRAMES = {
    "title": TIT2, "artist": TPE1, "album": TALB, "genre": TCON, "year": TDRC,
}


class TagsNotSupportedError(ValueError):
    """Raised when the format has no container that can carry tags (pcm, raw aac)."""


def _register_easyid3_comment() -> None:
    """Teach EasyID3 the ``comment`` key (it omits COMM by default — mutagen recipe)."""
    def getter(id3, key):
        return [f.text[0] for f in id3.getall("COMM") if f.desc == ""]

    def setter(id3, key, value):
        id3.delall("COMM")
        id3.add(COMM(encoding=3, lang="eng", desc="", text=value))

    def deleter(id3, key):
        id3.delall("COMM")

    EasyID3.RegisterKey("comment", getter, setter, deleter)


_register_easyid3_comment()


def _normalize(tags: dict) -> dict:
    """All six keys present as trimmed strings ("" means clear that field)."""
    tags = tags or {}
    return {k: str(tags.get(k) or "").strip() for k in TAG_KEYS}


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


def _write_mp3(path: str, t: dict) -> None:
    try:
        audio = EasyID3(path)
    except ID3NoHeaderError:
        audio = EasyID3()  # fresh tags; .save(path) writes the header (research D9)
    for key, ezkey in _EASYID3_KEYS.items():
        if t[key]:
            audio[ezkey] = t[key]
        elif ezkey in audio:
            del audio[ezkey]
    audio.save(path)


def _write_wav(path: str, t: dict) -> None:
    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    id3 = audio.tags
    for key, frame_cls in _WAV_FRAMES.items():
        id3.delall(frame_cls.__name__)
        if t[key]:
            id3.add(frame_cls(encoding=3, text=[t[key]]))
    id3.delall("COMM")
    if t["comment"]:
        id3.add(COMM(encoding=3, lang="eng", desc="", text=[t["comment"]]))
    audio.save()


def _write_vorbis(path: str, fmt: str, t: dict) -> None:
    audio = FLAC(path) if fmt == "flac" else OggOpus(path)
    if audio.tags is None:  # rare: a container with no comment block yet
        audio.add_tags()
    tags = audio.tags
    for key, field in _VORBIS_KEYS.items():
        if t[key]:
            tags[field] = [t[key]]
        elif field in tags:
            del tags[field]
    audio.save()
