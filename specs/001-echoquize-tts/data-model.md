# Phase 1 Data Model: Echoquize

**Date**: 2026-06-08 | **Feature**: 001-echoquize-tts

Derived from the spec's Key Entities and Functional Requirements. The only persisted entity is the
**Generation Record** (one SQLite table); the others are in-memory or abstract.

## Entity: Generation Record

Persisted in the `generations` table. One row per successfully generated audio file (FR-006). The
row is the source of truth for what the Library displays (FR-009); the file is authoritative for
external playback.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | TEXT (UUID4) | yes | Primary key |
| `text_input` | TEXT | yes | Source text, 1–4096 chars |
| `voice` | TEXT | yes | One of the 13 supported voices |
| `model` | TEXT | yes | `tts-1` \| `tts-1-hd` \| `gpt-4o-mini-tts` |
| `format` | TEXT | yes | `mp3 \| opus \| aac \| flac \| wav \| pcm` |
| `speed` | REAL | yes | 0.25–4.0 |
| `file_path` | TEXT | yes | Backend-relative path returned by `StorageBackend.save()` |
| `file_size` | INTEGER | no | Bytes written |
| `created_at` | TEXT (ISO-8601 UTC) | yes | Sort key (DESC) for the Library |
| `tag_title` | TEXT | no | Metadata tag |
| `tag_artist` | TEXT | no | Metadata tag |
| `tag_album` | TEXT | no | Metadata tag |
| `tag_comment` | TEXT | no | Metadata tag |
| `tag_genre` | TEXT | no | Metadata tag |
| `tag_year` | TEXT | no | Metadata tag (maps to `date` for EasyID3) |

### Schema (DDL)

```sql
CREATE TABLE IF NOT EXISTS generations (
  id          TEXT PRIMARY KEY,        -- UUID4
  text_input  TEXT NOT NULL,
  voice       TEXT NOT NULL,
  model       TEXT NOT NULL,
  format      TEXT NOT NULL,
  speed       REAL NOT NULL,
  file_path   TEXT NOT NULL,
  file_size   INTEGER,
  created_at  TEXT NOT NULL,           -- ISO-8601
  tag_title   TEXT,
  tag_artist  TEXT,
  tag_album   TEXT,
  tag_comment TEXT,
  tag_genre   TEXT,
  tag_year    TEXT
);
CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_voice ON generations(voice);
```

> Indexes back the Library's `ORDER BY created_at DESC` paging and the voice filter (SC-009, FR-009/010).

### Lifecycle (state transitions)

```
[form input] --validate--> [generating] --TTS bytes--> [saving file] --insert row--> [SAVED]
   SAVED --(optional)--> [tag-written]            (write_tags, taggable formats only)
   SAVED --(user)------> [deleted]                (single or bulk: row + file removed)
```

- A record exists **only** after both the file is saved and the row is inserted (no orphan rows).
- Deletion removes the row and calls `StorageBackend.delete(file_path)`; a missing file is tolerated
  (logged, deletion still succeeds — readiness CHK015).

## Entity: Tag Set (embedded)

Not a separate table — the six `tag_*` columns above. Mapping to file metadata by format
(see `contracts/tag-writer.md`):

| Logical key | EasyID3 (mp3/wav) | FLAC/Opus (Vorbis) | MP4 (n/a for raw aac) |
|-------------|-------------------|--------------------|-----------------------|
| title | `title` | `TITLE` | `©nam` |
| artist | `artist` | `ARTIST` | `©ART` |
| album | `album` | `ALBUM` | `©alb` |
| comment | `comment` | `COMMENT` | `©cmt` |
| genre | `genre` | `GENRE` | `©gen` |
| year | `date` | `DATE` | `©day` |

- Empty/None values are skipped (not written).
- `pcm` → `TagsNotSupportedError`; `aac` → unsupported (raw ADTS), surfaced as a UI notice.

## Entity: Batch Queue Item (ephemeral)

Held in `gr.State` per browser session; **not persisted** (lost on restart — acceptable per spec).

| Field | Type | Notes |
|-------|------|-------|
| `text` | str | 1–4096 chars (validated per item, not per batch — FR-022) |
| `voice` / `model` / `format` / `speed` | str/float | Same domains as a Generation Record |
| `instructions` | str | Only used when `model == gpt-4o-mini-tts` |
| `tags` | dict | Optional tag set applied after generation |

On "Generate All", each item becomes a Generation Record (and file) and is bundled into one zip
download (FR-008).

## Entity: Storage Destination (abstract)

Not persisted; selected by `STORAGE_BACKEND` env at startup (see `contracts/storage-backend.md`).
The user-facing experience is identical regardless of destination (SC-007).

## Validation Rules (from requirements)

| Rule | Source |
|------|--------|
| `text_input` non-empty and ≤ 4096 chars, checked **before** any TTS call | FR-022, FR-001 |
| In a batch, the limit applies **per item**, not to the total | FR-022, Edge Cases |
| `voice` ∈ {13 voices}; `model` ∈ {3 models}; `format` ∈ {6 formats}; `speed` ∈ [0.25, 4.0] | FR-002, research D4 |
| `instructions` sent only when `model == gpt-4o-mini-tts` | FR-003, research D4 |
| `pcm` → no inline preview (download-only) + notice | FR-004, Edge Cases |
| `pcm`/`aac` → tagging skipped with notice; generation still succeeds | FR-014 |
| Library page: `limit` default 50, `offset ≥ 0`, optional `voice` filter | FR-009, research D6 |
| Bulk delete requires explicit confirmation; removes row(s) + file(s) | FR-010, research D7 |
| Required config present at startup or fail fast (`OPENAI_API_KEY`) | FR-016, research D10 |
