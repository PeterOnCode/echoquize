# Phase 1 Data Model: TTS Studio Enhancements

**Date**: 2026-06-10 | **Feature**: 002-studio-enhancements

Deltas to the feature-001 data model. The only persisted entity remains the **Generation Record**
(one SQLite table); everything else is in-memory or configuration.

## Entity: Generation Record (extended)

Persisted in the `generations` table. This feature adds two columns and broadens the meaning of one
existing column. **No column is removed or renamed** (backward compatible, FR-037).

| Field | Type | Req | Change | Notes |
|-------|------|-----|--------|-------|
| `id` … `created_at` | — | — | unchanged | existing primary/data columns |
| `file_path` | TEXT | yes | **value shape changes** | now `…/YYYY/MM/DD/<title-slug>.<ext>`; still the backend path returned by `save()`/`rename()` |
| `tag_title` | TEXT | no | unchanged | TIT2 |
| `tag_artist` | TEXT | no | unchanged | TPE1 |
| `tag_album` | TEXT | no | unchanged | TALB |
| `tag_comment` | TEXT | no | unchanged | COMM |
| `tag_genre` | TEXT | no | unchanged | TCON |
| `tag_year` | TEXT | no | **meaning broadened** | now the **recording date/time** (TDRC); a bare year remains valid |
| `tag_track` | TEXT | no | **NEW** | TRCK; `"n"` or `"n/total"` |
| `tags_extra` | TEXT (JSON) | no | **NEW** | open-ended/multi-value frames (see below) |

### `tags_extra` JSON shape

```json
{
  "languages": ["eng", "hun"],
  "custom_text": [{ "desc": "MOOD", "value": "calm" }],
  "custom_url": [{ "desc": "source", "url": "https://example.org" }]
}
```

- Absent/empty keys are omitted; a fully empty set is stored as `NULL` (not `"{}"`).
- `languages` → `TLAN` (ID3) / `LANGUAGE` (Vorbis); `custom_text` → `TXXX` / Vorbis `<DESC>` key;
  `custom_url` → `WXXX` (ID3 only — skipped for Vorbis, R4).

### Schema (DDL after migration)

```sql
CREATE TABLE IF NOT EXISTS generations (
  id          TEXT PRIMARY KEY,
  text_input  TEXT NOT NULL,
  voice       TEXT NOT NULL,
  model       TEXT NOT NULL,
  format      TEXT NOT NULL,
  speed       REAL NOT NULL,
  file_path   TEXT NOT NULL,
  file_size   INTEGER,
  created_at  TEXT NOT NULL,
  tag_title   TEXT,
  tag_artist  TEXT,
  tag_album   TEXT,
  tag_comment TEXT,
  tag_genre   TEXT,
  tag_year    TEXT,
  tag_track   TEXT,        -- NEW
  tags_extra  TEXT         -- NEW (JSON)
);
-- indexes unchanged (created_at DESC, voice)
```

### Migration (additive, idempotent)

Runs in `init_db()` after the `CREATE TABLE IF NOT EXISTS`:

1. `cols = {row["name"] for row in PRAGMA table_info(generations)}`
2. For each of `tag_track`, `tags_extra` not in `cols`: `ALTER TABLE generations ADD COLUMN <c> TEXT`.

Existing rows receive `NULL` for the new columns and continue to work (their `tag_year` is already
a valid recording-date value). No backfill; no reading tags out of existing files (Principle V).

### Lifecycle (additions)

```
SAVED --(US5 rename)--> file moved within YYYY/MM/DD + file_path updated (collision-safe)
SAVED --(US2/US5 tag edit)--> full tag set re-written to file + tag_* / tag_track / tags_extra updated
```

- A rename updates `file_path` (and `file_size` is unaffected). The move and the DB update happen
  together; a missing source file surfaces a friendly error and leaves the record unchanged.
- Tag writes continue to "replace the full set"; clearing a field nulls its column / removes its
  `tags_extra` entry.

## Entity: Tag Set (expanded, embedded)

The logical tag set passed to/from `write_tags` (see `contracts/tag-writer.md`). Per-format
applicability:

| Logical key | ID3 (mp3/wav) | Vorbis (flac/opus) | aac/pcm |
|-------------|---------------|--------------------|---------|
| title | TIT2 | TITLE | — |
| artist | TPE1 | ARTIST | — |
| album | TALB | ALBUM | — |
| comment | COMM | COMMENT | — |
| genre | TCON | GENRE | — |
| date (was `year`) | TDRC | DATE | — |
| track | TRCK | TRACKNUMBER | — |
| languages[] | TLAN | LANGUAGE | — |
| custom_text[] | TXXX (desc/value) | `<DESC>` field | — |
| custom_url[] | WXXX (desc/url) | *(no equivalent — skipped + notice)* | — |

- ID3 (mp3/wav) is written explicitly as **ID3v2.4.0**.
- aac/pcm → `TagsNotSupportedError`; skipped with a notice, generation still completes.

## Entity: Batch Queue Item (extended, ephemeral)

Held in `gr.State` per session; **not persisted**. Now fully editable (US3) and bulk-creatable from
an uploaded file (US1).

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `text` | str | unchanged | 1–4096 chars, validated per item |
| `voice` / `model` / `format` / `speed` | str/float | unchanged | same domains |
| `instructions` | str | unchanged | only sent for `gpt-4o-mini-tts`; retained when model changes |
| `tags` | dict | **expanded** | the full Tag Set above; seeded from `DEFAULT_TAGS` on creation |

On "Generate all", each item becomes a Generation Record + file, named from its own title (slug),
and bundled into one zip (unchanged behavior plus slug naming + expanded tags).

## Entity: Default Tag Configuration (new, config-only)

Read from the environment at startup into `config.DEFAULT_TAGS` (see `contracts/config.md`). Not
persisted, not user-editable in the app.

| Env var | Maps to | Default |
|---------|---------|---------|
| `DEFAULT_TAG_ARTIST` | artist | unset → blank |
| `DEFAULT_TAG_ALBUM` | album | unset → blank |
| `DEFAULT_TAG_GENRE` | genre | unset → blank |
| `DEFAULT_TAG_COMMENT` | comment | unset → blank |
| `DEFAULT_TAG_LANGUAGE` | languages (single seed) | unset → blank |

Title is never defaulted. Invalid/unreadable values fall back to blank (FR-048).

## Entity: Application Version (new, derived)

Not persisted. Provided by `src/version.py` (`contracts/version.md`): the `[project].version` value
from `pyproject.toml`, surfaced next to the title and updated by `bump-my-version`. `None` when
undeterminable → omitted from the header.

## Validation Rules (additions)

| Rule | Source |
|------|--------|
| Uploaded file is UTF-8 text; split on newlines; blank/whitespace lines skipped | FR-002, FR-004 |
| Each uploaded line validated against 4096 chars; over-length rejected with line number; valid lines still added | FR-006 |
| Upload appends to the queue (never clears); summary reports added/skipped/rejected | FR-003, FR-007 |
| Filename stem = slug(title): NFKD→ASCII, lowercase, spaces→`_`, strip to `[a-z0-9_-]`, collapse/trim, ≤64 chars | FR-016 |
| Collision in target dated folder → append `_2`,`_3`… within 64-char cap; never overwrite | FR-017, FR-023 |
| Empty / empty-slug title → UUID stem fallback (generation); empty/empty-slug rename → rejected, original kept | FR-018, FR-040 |
| New audio stored under `YYYY/MM/DD` from UTC `created_at`; uniform across backends; existing files untouched | FR-021, FR-022, FR-024 |
| ID3 (mp3/wav) written as v2.4.0; FLAC/Opus map where possible, skip otherwise with notice; aac/pcm skipped | FR-033, FR-035, FR-036 |
| Recording date accepts full timestamp or year-only | FR-034 |
| Tag values persisted in DB (columns + `tags_extra` JSON); existing rows keep working | FR-037 |
| Custom text/URL entries are description-keyed; multiple entries coexist | FR-038 |
| Library rename = manual, slug-validated, collision-safe; extension not editable; title edit never auto-renames | FR-040, FR-041, FR-042 |
| Default tags pre-fill Generate fields + seed new queue items; title never defaulted; defaults overridable | FR-044–FR-047 |
| Version read at runtime from single source; undeterminable → omit, never error at startup | FR-025, FR-026 |
