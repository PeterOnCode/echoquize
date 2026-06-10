# Contract: Tag Writer (`src/tags/writer.py`, delta)

Extends the feature-001 writer to the expanded ID3v2.4.0 frame set (US2), writing MP3/WAV
explicitly as **ID3 v2.4.0**. Keeps the "replace the full tag set on every call" semantics and the
`TagsNotSupportedError` behavior for aac/pcm (Principle VII).

## Tag input shape

`write_tags(file_path: str, fmt: str, tags: dict) -> None` — `tags` is the expanded logical set:

```python
{
  "title": str, "artist": str, "album": str, "comment": str, "genre": str,
  "date": str,            # was "year"; full timestamp OR year-only (FR-034)
  "track": str,           # "n" or "n/total"
  "languages": [str, ...],            # ISO 639-2 codes
  "custom_text": [{"desc": str, "value": str}, ...],
  "custom_url":  [{"desc": str, "url": str}, ...],
}
```

- Missing keys / empty strings / empty lists mean "clear that frame".
- Backward compatibility: a legacy `"year"` key is accepted as an alias for `"date"`.

## Per-format behavior

| Format | How |
|--------|-----|
| `mp3` | raw `ID3` frames: `TIT2/TPE1/TALB/TCON/COMM/TDRC/TRCK/TLAN/TXXX/WXXX`; `audio.save(path, v2_version=4)` |
| `wav` | same ID3 frames on the `WAVE` tag block; saved as v2.4 |
| `flac`, `opus` | Vorbis comments: `TITLE/ARTIST/ALBUM/COMMENT/GENRE/DATE/TRACKNUMBER/LANGUAGE` + `custom_text` as `<DESC>` fields; **`custom_url` has no equivalent → skipped, surfaced as a notice by the caller** |
| `aac`, `pcm` | `raise TagsNotSupportedError` (unchanged) |

- **ID3 v2.4.0 is explicit** (FR-033): pass `v2_version=4` on save (also the mutagen default, made
  explicit to resist drift).
- Multi-value `languages` → one `TLAN` with multiple values (ID3) / repeated `LANGUAGE` (Vorbis).
- `custom_text` → one `TXXX` per entry keyed by `desc`; `custom_url` → one `WXXX` per entry keyed by
  `desc`.

## Errors & guarantees

- aac/pcm → `TagsNotSupportedError`; caller skips with a notice and the generation still completes
  (FR-035, FR-036).
- For FLAC/Opus, frames with no equivalent (custom URL) are skipped silently in the writer and the
  caller emits a notice — never an exception.
- Light validation only (e.g. coerce values to strings); bad input is rejected by the caller with a
  friendly message, never a traceback (Principle VII).
- Writing is idempotent and full-replace: re-writing the same `tags` yields the same file tags;
  clearing a field removes its frame.

> Persistence of these values is the database's job, not the writer's — see
> [database.md](./database.md). The writer only touches the file.
