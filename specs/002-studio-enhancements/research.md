# Phase 0 Research: TTS Studio Enhancements

**Date**: 2026-06-10 | **Feature**: 002-studio-enhancements

Resolves the technical unknowns in the plan's Technical Context. Each decision is grounded in the
existing feature-001 code and the constitution. No NEEDS CLARIFICATION markers remain.

---

## R1 — Title-to-filename slug & transliteration

**Decision**: Implement slugging in a new pure module `src/naming.py` using the **standard library
only**: `unicodedata.normalize("NFKD", title)` then `.encode("ascii", "ignore").decode()` to
transliterate accented Latin characters (é→e, ñ→n, ü→u); then lowercase, replace whitespace runs
with `_`, drop every character outside `[a-z0-9_-]`, collapse repeated separators, trim leading/
trailing `_`/`-`, and truncate to 64 chars. If the result is empty, the caller falls back to a
UUID stem.

**Rationale**: NFKD + ASCII-ignore exactly matches the spec: Latin accents are transliterated, and
non-Latin scripts (CJK, Arabic) drop to empty → the intended UUID fallback. No third-party library
is needed, honoring Principles II (no new pinned dep) and VI (no speculative complexity).

**Alternatives considered**: `unidecode` / `python-slugify` — richer romanization (e.g. Cyrillic →
Latin), but adds a runtime dependency for behavior the spec explicitly does *not* require (it wants
non-Latin titles to fall back to a UUID). Rejected.

---

## R2 — Where filename uniqueness/collision lives (Principle I)

**Decision**: `StorageBackend.save(data, filename)` becomes **collision-safe internally**: if
`filename` already exists in the computed target folder, the backend appends `_2`, `_3`, … to the
stem (keeping the whole stem ≤ 64 chars) and returns the actual stored path. Callers compute the
desired stem (via `src/naming.py`) and pass `f"{stem}.{ext}"`; they never inspect the directory or
build paths.

**Rationale**: Uniqueness "within the dated folder" requires knowing the folder, which is
storage-internal. Putting collision logic in the backend keeps the layout knowledge behind the
abstraction (Principle I). UUID filenames (used as the fallback and for the existing flow) simply
never collide, so the suffix path is exercised only by slug names.

**Alternatives considered**: Resolve collisions in the UI by pre-checking existence — rejected: it
forces callers to know the filesystem layout, violating Principle I, and is racy.

---

## R3 — Day-level folder layout (`YYYY/MM/DD`) across backends

**Decision**: Change the path/key convention from `YYYY/MM/` to `YYYY/MM/DD/` **inside each
backend**. `LocalStorage.save()` adds `/ {now:%d}` to the subdir (one line). The date basis is the
generation's creation moment in **UTC** (`datetime.now(timezone.utc)`), matching how `created_at`
is already stored. S3/GDrive stubs document the same key convention. The collision check (R2) is
scoped to the day folder for free, since the suffixing happens after the folder is computed.

**Rationale**: Layout stays in storage (Principle I). UTC keeps the folder date consistent with the
DB sort/filter key (which is tz-naive UTC). Backend-uniform layout satisfies FR-022.

**Alternatives considered**: Pass the dated subpath from the caller — rejected (Principle I).

---

## R4 — Expanded ID3v2.4.0 tags with mutagen (US2)

**Decision**: Extend `src/tags/writer.py` to the full logical set: `title, artist, album, comment,
genre, date` (the existing `year` generalized to a date/time string), plus new `track`,
`languages` (list), `custom_text` (list of `{desc, value}`), `custom_url` (list of `{desc, url}`).

- **MP3**: write via the raw `ID3` API (not only EasyID3) so `TXXX`/`WXXX` and multi-value `TLAN`
  are expressible; call `audio.save(path, v2_version=4)` to pin **ID3v2.4.0** explicitly.
- **WAV**: same raw-ID3 frames on the `WAVE` tag block, saved as v2.4.
- **FLAC/Opus (Vorbis)**: map `track→TRACKNUMBER`, `languages→LANGUAGE`, `date→DATE`,
  `custom_text→<DESC>` (description becomes the field name); **`custom_url` (WXXX) has no clean
  Vorbis equivalent and is skipped with a notice**. Existing fields map as today.
- **AAC/PCM**: unchanged — `TagsNotSupportedError`, skipped with a notice.

`write_tags` keeps its "replace the full set on every call" semantics; an empty value clears its
frame.

**Rationale**: mutagen already defaults `ID3.save` to `v2_version=4`; making it explicit satisfies
FR-033 and is robust against version drift. Raw frames are required for `TXXX`/`WXXX`/multi-value
`TLAN`, which EasyID3 does not cleanly model.

**Alternatives considered**: Stay on EasyID3 only — rejected: cannot express custom/URL/multi-value
frames. A separate MP4/M4A path for AAC — rejected: OpenAI returns raw ADTS, not an M4A box
(unchanged constraint).

---

## R5 — Tag persistence schema & migration (US2/US5)

**Decision**: The database stays the source of truth for tags. Extend `generations` additively:

- keep the six existing `tag_*` columns; `tag_year` now stores the full recording date/time string
  (a year remains valid) — **no rename**, so old rows keep working;
- add `tag_track TEXT`;
- add `tags_extra TEXT` holding a JSON object for the open-ended/multi-value frames:
  `{"languages": [...], "custom_text": [{"desc","value"}...], "custom_url": [{"desc","url"}...]}`.

Migration runs in `init_db()`: after `CREATE TABLE IF NOT EXISTS`, read `PRAGMA table_info` and
`ALTER TABLE generations ADD COLUMN` for any missing new column. Existing rows get `NULL`.

**Rationale**: Additive `ADD COLUMN` is the safe, idempotent SQLite migration and preserves all
data (Principle V). One JSON column avoids a child table for arbitrary/repeatable frames, fitting
the pragmatic single-user scope (Principle VI). The editor reads columns (today's behavior), so new
tags must be persisted to be re-editable (this is what US5 depends on).

**Alternatives considered**: A normalized `generation_tags` child table — rejected as
over-engineering for a single-user tool. Re-reading tags from files via mutagen instead of the DB —
rejected: introduces a read pattern the app does not have today and is awkward for custom frames.

---

## R6 — Version source for the UI (US8)

**Decision**: New module `src/version.py` reads `[project].version` from `pyproject.toml` using
stdlib `tomllib`, resolving the file relative to the repo root. It first tries
`importlib.metadata.version("echoquize")` and falls back to the `pyproject.toml` read; if both
fail it returns `None`, and the header omits the version.

**Rationale**: `pyproject.toml` has **no `[build-system]`**, so the project is not installed as a
distribution and `importlib.metadata` is unreliable — reading the file is the dependable source.
`tomllib` is stdlib on 3.12 (no new dep). The `None`/omit fallback satisfies FR-026 (never error at
startup).

**Alternatives considered**: Hardcode the version in the UI — rejected (drifts from releases,
violates the single-source-of-truth requirement and the spec). `importlib.metadata` alone —
rejected (unreliable without a build backend).

---

## R7 — `bump-my-version` adoption (US6/US9)

**Decision**: Add `bump-my-version` as a **dev dependency** (`uv add --dev bump-my-version`, commit
the updated `uv.lock`). Configure `[tool.bumpversion]` in `pyproject.toml` with
`current_version = "0.1.0"`, `commit = true`, `tag = true`, and a `[[tool.bumpversion.files]]` rule
that updates `version = "…"` in the `[project]` table (the single source of truth read by
`src/version.py`). Add `justfile` recipes `bump-patch` / `bump-minor` / `bump-major` wrapping
`uv run bump-my-version bump <part>`.

**Rationale**: Dev dependency keeps the tool pinned/reproducible with the project (Principle II) and
out of the runtime image. Updating the `[project].version` field means a bump is automatically
reflected by `src/version.py` with no extra change (FR-030). Commit+tag satisfy FR-029.

**Alternatives considered**: `uv tool install bump-my-version` (global) — rejected: not pinned with
the project. A hand-written bump script — rejected: reinvents the requested tool.

---

## R8 — Per-row batch-queue editing UX (US3)

**Decision**: Reuse the existing select-row pattern. The queue `gr.Dataframe` already emits a
`.select` event into `selected_index` (`generate_tab.py`). Add an "Edit selected item" panel
(mirroring the Library tag editor) that, on row select, loads that item's fields (text, voice,
model, format, instructions, the expanded tags) into editable widgets; an "Update item" button
writes the edited values back into the `queue_state` list at that index and refreshes the queue
view. Text edits re-run the 4096-char validation. Voice-instructions/tag visibility follows the
same model/format rules as the single-generate form.

**Rationale**: Editing many fields (incl. ~10 tag fields) inline in dataframe cells is unwieldy;
the select → edit-panel → update flow matches a pattern already in the codebase, keeping the UI
consistent and the change small (Principle VI).

**Alternatives considered**: Fully inline-editable dataframe — rejected: poor fit for dropdowns and
many tag fields; harder to validate per field.

---

## R9 — Batch-queue file upload (US1)

**Decision**: Add a `gr.File(file_types=[".txt"])` (or `gr.UploadButton`) to the Batch queue
accordion. On upload, read the file bytes, decode as UTF-8, `splitlines()`, strip each line, drop
blanks, and for each remaining line build a queue item that inherits the current form's
voice/model/format/speed (and default tags per US7). Validate each line against `MAX_CHARS`;
collect rejected line numbers. Append valid items to `queue_state` (never replace). Return a
summary string: added / blank-skipped / rejected-too-long counts (with rejected line numbers).

**Rationale**: Parsing is pure and in-process (no API calls), so even large files stay responsive
(FR-008). Appending and the summary satisfy FR-002–FR-007.

**Alternatives considered**: Stream/generate on upload — rejected: the spec requires queue
population only; generation stays behind "Generate all".

---

## R10 — Default tag values (US7)

**Decision**: `config.py` reads optional `DEFAULT_TAG_ARTIST`, `DEFAULT_TAG_ALBUM`,
`DEFAULT_TAG_GENRE`, `DEFAULT_TAG_COMMENT`, `DEFAULT_TAG_LANGUAGE` (blank/`None` when unset) into a
`DEFAULT_TAGS` mapping. The Generate tab initializes its tag widgets' `value=` from these, and
newly added queue items (manual or from upload) seed their tags from the same mapping. Title is
never defaulted. Unreadable/invalid values fall back to blank.

**Rationale**: Config-as-environment (Principle III); no new persistence surface (Principle VI);
blank fallback satisfies FR-048. `.env.example` documents the new optional keys.

**Alternatives considered**: An in-app editable settings screen — rejected: introduces a new
persisted user-settings surface the app does not have, beyond the requirement.

---

## R11 — Library "edit details" (rename + expanded tags) (US5)

**Decision**: Replace the Library "Edit tags" accordion with an "Edit details" panel. On row
select it loads the current filename **stem** (parsed from `os.path.basename(file_path)` minus
extension) plus the full expanded tag set. "Save" does: (1) if the stem changed, slug-normalize it
(R1), call the new `StorageBackend.rename(old_path, f"{stem}.{ext}")` which moves the file
collision-safely within its dated folder and returns the new path, then `update_file_path(gid,
new_path)`; (2) write the expanded tags to the file and `update_tags`/`tags_extra` in the DB. Empty
or un-sluggable stems are rejected (original kept); the extension field is read-only; editing the
title never triggers a rename.

**Rationale**: Renaming is a storage operation, so it goes through the backend (Principle I). Reuses
the existing select-and-save pattern. Satisfies FR-039–FR-043.

**Alternatives considered**: Free-form rename bypassing slug rules — rejected: would let invalid/
duplicate names onto disk; the spec requires the same slug rules and collision safety as US4.

---

## Summary of new/changed surfaces

| Area | Change | Stories |
|------|--------|---------|
| `src/naming.py` (new) | `slugify(title) -> str` (stdlib only) | US3, US4, US5 |
| `src/version.py` (new) | `app_version() -> str | None` (stdlib tomllib) | US8 |
| `src/storage/base.py` | add `rename()`; `save()` collision-safe | US3, US4, US5 |
| `src/storage/local.py` | `YYYY/MM/DD` + collision suffix + rename | US4, US3, US5 |
| `src/storage/{s3,gdrive}.py` | `rename()` stub (`NotImplementedError`) | — |
| `src/tags/writer.py` | expanded frames, explicit ID3v2.4.0, Vorbis mapping | US2 |
| `src/db/database.py` | `tag_track`+`tags_extra` columns, migration, `update_file_path` | US2, US5 |
| `config.py` | `DEFAULT_TAG_*` reads | US7 |
| `src/ui/generate_tab.py` | upload, per-row edit, expanded+default tags, slug filename | US1, US2, US3, US4, US7 |
| `src/ui/library_tab.py` | "edit details" panel (rename + expanded tags) | US5 |
| `app.py` | version next to title | US8 |
| `pyproject.toml` / `justfile` / `uv.lock` | bump-my-version dev dep, config, recipes | US6, US9 |
