# Contract: src/tags/writer.py

Writes metadata tags into audio files using mutagen, format-aware. (Principle VII.)

## Signature

```python
class TagsNotSupportedError(ValueError): ...

def write_tags(file_path: str, fmt: str, tags: dict) -> None: ...
```

`tags` keys: `title`, `artist`, `album`, `comment`, `genre`, `year`. Empty/None values are skipped.

## Format mapping

| `fmt` | mutagen class | Tag style |
|-------|---------------|-----------|
| `mp3` | `mutagen.easyid3.EasyID3` | ID3 (EasyID3; `year` → `date`) |
| `wav` | `mutagen.wave.WAVE` + ID3 | ID3 in WAV (some players ignore — UI tooltip) |
| `flac` | `mutagen.flac.FLAC` | VorbisComment |
| `opus` | `mutagen.oggopus.OggOpus` | OpusTags |
| `aac` | — | **Unsupported** (raw ADTS, not M4A) → notice, not written |
| `pcm` | — | `raise TagsNotSupportedError` (no container) |

## Behavior / guarantees

- New MP3 with no ID3 header: handle `mutagen.id3.ID3NoHeaderError` by creating tags then saving
  (no crash — research D9).
- `pcm` → `TagsNotSupportedError`; callers show "Tags are not supported for PCM format — skipped"
  and still complete generation (FR-014).
- `aac` → treated as unsupported with a clear notice; generation still completes.
- Writing is idempotent; re-writing replaces existing tag values.

## Contract tests (manual)

- `write_tags("x.mp3", "mp3", {"title": "Hello", "artist": "Echo"})` → tags readable in VLC.
- `write_tags("x.pcm", "pcm", {})` → raises `TagsNotSupportedError`.
