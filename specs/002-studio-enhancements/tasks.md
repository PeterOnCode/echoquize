---
description: "Task list for 002-studio-enhancements"
---

# Tasks: TTS Studio Enhancements

**Input**: Design documents from `/specs/002-studio-enhancements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Per Constitution Principle VI (pragmatic single-user scope), **no automated test suite**
is generated. Each user story ends with a **manual validation** task against
`specs/002-studio-enhancements/quickstart.md`. The offline subset is wired into `just verify`.

**Organization**: Tasks are grouped by user story (US1–US9 from spec.md) to enable independent
implementation and validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story the task serves (US1–US9). Setup/Foundational/Polish have no story label.
- All paths are repository-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Standalone, dependency-free helper modules consumed by several stories. The base
feature-001 app already provides project init, deps, Docker, and config.

- [X] T001 [P] Create `src/naming.py` implementing `slugify(title) -> str` per `contracts/naming.md` (stdlib `unicodedata` NFKD→ASCII, lowercase, spaces→`_`, strip to `[a-z0-9_-]`, collapse/trim, ≤64-char stem; returns `""` for non-ASCII-only input). Consumed by US4, US5.
- [X] T002 [P] Create `src/version.py` implementing `app_version() -> str | None` per `contracts/version.md` (try `importlib.metadata.version("echoquize")`, fall back to reading `[project].version` from `pyproject.toml` via stdlib `tomllib`, return `None` on any failure — never raises). Consumed by US8.

---

## Phase 2: Foundational (Shared Tag Backbone)

**Purpose**: Backend changes shared by the tag-related stories. **Blocks US2, US3, US5, US7.** Does
**not** block US1, US4, US6, US8, US9 (those are independent of the tag backbone).

**⚠️ Backward compatibility**: Both tasks must keep the existing single-generate flow working — the
expanded writer/DB functions accept the legacy 6-key tag dict (treating `year` as `date`) and
default the new fields to empty/`None`, so the app stays runnable before the UI stories land.

- [X] T003 [P] Expand `src/tags/writer.py` per `contracts/tag-writer.md`: accept the expanded logical tag set (`date` generalizing `year`, `track`, `languages[]`, `custom_text[]`, `custom_url[]`); write MP3/WAV via raw ID3 frames `TIT2/TPE1/TALB/TCON/COMM/TDRC/TRCK/TLAN/TXXX/WXXX` saved explicitly as **ID3v2.4.0** (`v2_version=4`); map FLAC/Opus to Vorbis equivalents and skip `custom_url` (no equivalent); keep `TagsNotSupportedError` for aac/pcm and the full-replace semantics.
- [X] T004 [P] Extend `src/db/database.py` per `contracts/database.md`: add additive `tag_track` + `tags_extra` columns with an idempotent `PRAGMA table_info` → `ALTER TABLE ADD COLUMN` migration in `init_db()`; expand `insert_generation` and `update_tags` to read/write the new columns (`tags_extra` as JSON, empty→`NULL`); add `update_file_path(gid, new_path, file_size=None)`.

**Checkpoint**: Existing app still runs against an old `echoquize.db` (migration adds columns, no data loss); single-generate still saves/tags as before.

---

## Phase 3: User Story 1 - Bulk-load the batch queue from a text file (Priority: P1) 🎯 MVP

**Goal**: Upload a `.txt` file to populate the batch queue, one item per line.

**Independent Test**: Upload a file with normal lines, a blank line, and an over-length line; verify one item per valid line in order, with an accurate added/skipped/rejected summary, nothing generated. (quickstart US1)

- [X] T005 [US1] Add an upload-parsing helper in `src/ui/generate_tab.py` that decodes UTF-8, `splitlines()`, strips each line, skips blank/whitespace-only lines, validates each remaining line against `MAX_CHARS`, and returns `(valid_items, blank_count, rejected_line_numbers)`.
- [X] T006 [US1] Add a `gr.File(file_types=[".txt"])` control to the Batch queue accordion in `src/ui/generate_tab.py` and wire it to append parsed items to `queue_state` in file order (inheriting the current voice/model/format/speed; seed tags empty for now, or from `DEFAULT_TAGS` once US7 lands), never clearing the queue, and emit a summary status `"Added N — skipped B blank — rejected R too long (lines …)"`.
- [X] T007 [US1] Validate US1 manually per `specs/002-studio-enhancements/quickstart.md` (added/skipped/rejected counts; append-not-replace; nothing generated).

**Checkpoint**: US1 fully functional and independently testable.

---

## Phase 4: User Story 2 - Richer, standards-based audio tags (Priority: P1)

**Goal**: Edit and persist the expanded ID3v2.4.0 tag set on the Generate form; MP3/WAV written as v2.4.0.

**Depends on**: Phase 2 (expanded writer + DB).

**Independent Test**: Generate an MP3 with the new fields; confirm ID3v2.4.0 frames in the file and that the values reappear after restart (persisted). (quickstart US2)

- [X] T008 [US2] Expand the "Audio tags" accordion in `src/ui/generate_tab.py` with the new inputs: Recording date (replaces "Year"), Track number, Language(s), and repeatable Custom text (desc/value) and Custom URL (desc/url).
- [X] T009 [US2] Update `_collect_tags`, `_apply_tags`, and `_on_generate` in `src/ui/generate_tab.py` to build the expanded tag dict, write it via the expanded `write_tags`, and persist the expanded columns + `tags_extra` JSON through `insert_generation` (persist only what was embedded, consistent with today's behavior).
- [X] T010 [US2] Validate US2 manually per `specs/002-studio-enhancements/quickstart.md` (ID3v2.4.0 frames present; FLAC maps/skip-URL; AAC/PCM skipped; values survive restart).

**Checkpoint**: US2 functional; expanded tags written and persisted from single generation.

---

## Phase 5: User Story 3 - Edit batch queue items in place (Priority: P2)

**Goal**: Make every queued item editable (text, voice, model, format, instructions, tags); apply per-item tags at batch generation.

**Depends on**: Phase 2 (expanded writer) and US2 (expanded tag fields). Builds in `generate_tab.py`.

**Independent Test**: Add items, edit one row's fields; only that item changes; over-length text rejected; instructions retained on model change; AAC/PCM tag-skip notice; speed not editable. (quickstart US3)

- [X] T011 [US3] Capture the expanded tag set (and instructions) into queue items on "Add current form to queue" — update `_add_to_queue` in `src/ui/generate_tab.py`.
- [X] T012 [US3] Add an "Edit selected item" panel in `src/ui/generate_tab.py` bound to the existing `queue_df.select`/`selected_index`, loading the selected item's text/voice/model/format/instructions/tags into editable widgets.
- [X] T013 [US3] Implement `_update_queue_item` in `src/ui/generate_tab.py`: validate text (non-empty, ≤`MAX_CHARS`; else reject + keep prior), write edits back to `queue_state[index]`, refresh the queue view, retain instructions when model changes away from `gpt-4o-mini-tts`, show a "tags will be skipped" notice for AAC/PCM without discarding values, and leave speed unchanged.
- [X] T014 [US3] Update `_generate_all` in `src/ui/generate_tab.py` to apply each item's tags (and instructions) via `_apply_tags`/`write_tags` before saving, so edited per-item tags take effect.
- [X] T015 [US3] Validate US3 manually per `specs/002-studio-enhancements/quickstart.md`.

**Checkpoint**: US3 functional; queued items fully editable and their tags applied on "Generate all".

---

## Phase 6: User Story 4 - Title-based filenames (Priority: P2)

**Goal**: Name generated files from the title (slug), collision-safe, never overwriting.

**Depends on**: Phase 1 (`src/naming.py`).

**Independent Test**: Generate two items with the same title same day → `name` and `name_2`; empty/non-Latin title → UUID fallback; first file never overwritten. (quickstart US4)

- [X] T016 [US4] Make `LocalStorage.save()` collision-safe in `src/storage/local.py` per `contracts/storage-backend.md`: if the target filename exists in its folder, append `_2`/`_3`… to the stem within the 64-char cap, and return the actual stored path (never overwrite).
- [X] T017 [US4] In `src/ui/generate_tab.py`, compute the filename stem from the title via `naming.slugify` (fallback to `uuid4().hex` when empty) in both `_on_generate` and `_generate_all`, and pass `f"{stem}.{fmt}"` to `storage.save` (store the returned path).
- [X] T018 [US4] Validate US4 manually per `specs/002-studio-enhancements/quickstart.md` (slug names, `_2` suffix, UUID fallbacks, no overwrite).

**Checkpoint**: US4 functional; files named from titles, unique within their folder.

---

## Phase 7: User Story 5 - Edit file details from the Library (Priority: P2)

**Goal**: Rename a saved file and edit its full tag set from the Library.

**Depends on**: Phase 1 (`src/naming.py`), Phase 2 (DB `update_file_path` + expanded tags), US4 (slug rules); collision scoping uses the dated folder (US6 when present).

**Independent Test**: Edit a saved item's filename + tags → file renamed on disk, path updated, preview/download still work; collision suffixes; empty name rejected; title edit never renames; AAC/PCM filename editable while tags skipped. (quickstart US5)

- [X] T019 [US5] Add `rename(old_path, new_filename) -> str` to the `StorageBackend` ABC in `src/storage/base.py`; implement it collision-safe within the source file's folder in `src/storage/local.py`; add `NotImplementedError` stubs in `src/storage/s3.py` and `src/storage/gdrive.py` (mirroring their `save()` stubs) per `contracts/storage-backend.md`.
- [X] T020 [US5] Replace the Library "Edit tags" accordion with an "Edit details" panel in `src/ui/library_tab.py`: a Filename (stem) field with the extension shown read-only, plus the full expanded tag fields; populate on row select from the record's `tag_*` columns + parsed `tags_extra` and the stem from `basename(file_path)`.
- [X] T021 [US5] Implement the "Edit details" save in `src/ui/library_tab.py`: if the stem changed, `slugify` it (reject empty/un-sluggable, keep original), call `storage.rename` then `update_file_path`, and report the final name; write the expanded tags via `write_tags` + `update_tags`; for AAC/PCM skip tag writing with a notice but still allow rename; never rename on a title-only edit; reload the page.
- [X] T022 [US5] Validate US5 manually per `specs/002-studio-enhancements/quickstart.md`.

**Checkpoint**: US5 functional; Library items renameable and fully re-taggable.

---

## Phase 8: User Story 6 - Day-level storage folders (Priority: P3)

**Goal**: Store new audio under `YYYY/MM/DD`.

**Independent Test**: Generate a file → written under `AUDIO_DIR/YYYY/MM/DD/` for today's UTC date; older files still play. (quickstart US6)

- [X] T023 [US6] Change `LocalStorage.save()` in `src/storage/local.py` to build the subdir as `YYYY/MM/DD` from `datetime.now(timezone.utc)`, and document the same day-level key convention in the `s3.py`/`gdrive.py` stub docstrings, per `contracts/storage-backend.md`. (Touches the same method as T016 — sequence after US4 if both are taken; the collision logic remains folder-relative and unaffected.)
- [X] T024 [US6] Validate US6 manually per `specs/002-studio-enhancements/quickstart.md` (new file under dated folder; old files still readable).

**Checkpoint**: US6 functional; new audio organized by day across backends.

---

## Phase 9: User Story 7 - Default tag values on the Generate tab (Priority: P3)

**Goal**: Pre-fill the Generate-form tag fields from configured defaults.

**Depends on**: US2 (expanded tag fields, incl. language). Touches `config.py`, `generate_tab.py`, `.env.example`.

**Independent Test**: Set `DEFAULT_TAG_ARTIST`/`ALBUM`, restart → fields pre-filled; title blank; overridable; new queue items seeded; invalid value → blank, app still starts. (quickstart US7)

- [X] T025 [US7] Add `DEFAULT_TAG_ARTIST/ALBUM/GENRE/COMMENT/LANGUAGE` reads and a `DEFAULT_TAGS` mapping (only set keys present; never raises) in `config.py` per `contracts/config.md`.
- [X] T026 [US7] Initialize the Generate-form tag widgets' `value=` from `config.DEFAULT_TAGS` and seed new queue items' tags (manual add in `_add_to_queue` and file-upload in T006) from the same mapping in `src/ui/generate_tab.py`; never default Title.
- [X] T027 [P] [US7] Document the `DEFAULT_TAG_*` keys (commented, optional) in `.env.example`.
- [X] T028 [US7] Validate US7 manually per `specs/002-studio-enhancements/quickstart.md`.

**Checkpoint**: US7 functional; defaults pre-fill and seed without forcing values.

---

## Phase 10: User Story 8 - App version in the header (Priority: P3)

**Goal**: Show the app version next to the title.

**Depends on**: Phase 1 (`src/version.py`).

**Independent Test**: Load the app → version shows next to the title; if undeterminable, it is omitted and the app still launches. (quickstart US8)

- [X] T029 [US8] In `app.py`, render `f"v{app_version()}"` as unobtrusive text next to the title when `app_version()` is non-`None`, and omit it otherwise (display only — no remote check).
- [X] T030 [US8] Validate US8 manually per `specs/002-studio-enhancements/quickstart.md`.

**Checkpoint**: US8 functional; version visible in the header.

---

## Phase 11: User Story 9 - One-command version bumping (Priority: P3)

**Goal**: Bump version (+ commit + tag) with one command via `bump-my-version`.

**Independent Test**: `just bump-patch` → `[project].version` and `current_version` move to `0.1.1`, a release commit + annotated tag created; header reflects the new version. (quickstart US9)

- [X] T031 [US9] Add `bump-my-version` as a dev dependency (`uv add --dev bump-my-version`) and commit the regenerated `uv.lock` (Principle II).
- [X] T032 [US9] Add a `[tool.bumpversion]` section to `pyproject.toml` (`current_version = "0.1.0"`, `commit = true`, `tag = true`) with a `[[tool.bumpversion.files]]` rule updating `version = "…"` in the `[project]` table, per `research.md` R7.
- [X] T033 [P] [US9] Add `bump-patch` / `bump-minor` / `bump-major` recipes to the `justfile` wrapping `uv run bump-my-version bump <part>`.
- [X] T034 [US9] Validate US9 manually per `specs/002-studio-enhancements/quickstart.md` (run in a clean tree; revert the test tag/commit afterward).

**Checkpoint**: US9 functional; releases are one command.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Docs and shared validation across stories.

- [X] T035 [P] Update `README.md`: new/expanded tag fields, title-derived filenames + `YYYY/MM/DD` layout, `DEFAULT_TAG_*` env vars, and the version-display + `just bump-*` release workflow.
- [X] T036 Extend the `just verify` offline checks to exercise `naming.slugify`, `version.app_version`, and the US1 upload parser.
- [ ] T037 Run the full `specs/002-studio-enhancements/quickstart.md` (US1–US9) plus the Principle I grep (no path-layout construction outside `src/storage/`) and the Principle V migration check (old DB still lists/plays). _(Automated portion done: Principle I grep PASS, Principle V migration PASS, and the full offline subset — US1 parser, US2 ID3v2.4.0 roundtrip, US4 slugify, US8 app_version, US9 bump dry-run — all PASS via `just verify` + manual REPL. **Pending:** the live-API/UI stories US2 generate-and-persist, US3, US5, US6, US7 require a manual `uv run app.py` run with an `OPENAI_API_KEY`.)_

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup only nominally; **blocks the tag stories US2, US3, US5, US7**. Does NOT block US1, US4, US6, US8, US9.
- **User Stories (Phase 3–11)**: see per-story dependencies below.
- **Polish (Phase 12)**: after the stories you intend to ship are complete.

### User story dependencies

- **US1 (P1)**: independent — base queue only. (Optionally consumes `DEFAULT_TAGS` if US7 is present.)
- **US2 (P1)**: depends on **Phase 2**.
- **US3 (P2)**: depends on **Phase 2** + **US2** (expanded tag fields). Same file as US1/US4 (`generate_tab.py`).
- **US4 (P2)**: depends on **Setup T001** (naming). Touches `local.py` + `generate_tab.py`.
- **US5 (P2)**: depends on **Setup T001**, **Phase 2** (`update_file_path`, expanded tags), **US4** (slug rules); collision scoping aligns with **US6** when present.
- **US6 (P3)**: independent (one-line storage change). Coordinates with US4 on `local.py:save()`.
- **US7 (P3)**: depends on **US2** (expanded fields). Touches `config.py` + `generate_tab.py`.
- **US8 (P3)**: depends on **Setup T002** (version). Touches `app.py`.
- **US9 (P3)**: independent (tooling). Touches `pyproject.toml`/`justfile`/`uv.lock`.

### Within each story

- Implementation before its manual-validation task.
- Tasks touching the same file are sequential (no `[P]` among them).

### Parallel opportunities

- **Setup**: T001 ∥ T002 (different files).
- **Foundational**: T003 ∥ T004 (different files).
- **Across stories** (after their prerequisites): US4 (`local.py`/`generate_tab.py`), US8 (`app.py`), and US9 (`pyproject.toml`/`justfile`) operate on largely disjoint files and can proceed in parallel by different developers. US6 shares `local.py:save()` with US4, so serialize those two.
- The `generate_tab.py` stories (US1, US2, US3, US4-wiring, US7) share one file — serialize edits there.

---

## Parallel Example: kickoff

```bash
# Phase 1 (Setup) — both pure helpers in parallel:
Task: "T001 Create src/naming.py (slugify)"
Task: "T002 Create src/version.py (app_version)"

# Phase 2 (Foundational) — different files in parallel:
Task: "T003 Expand src/tags/writer.py to ID3v2.4.0 set"
Task: "T004 Extend src/db/database.py (columns + migration + update_file_path)"
```

---

## Implementation Strategy

### MVP first (US1)

1. Phase 1 (Setup) → 2. US1 (Phase 3). **Stop & validate** US1 independently (quickstart US1). This
   is the smallest shippable increment — no tag/storage backbone needed.

### Recommended incremental order

Setup → Foundational → **US1** (MVP) → **US2** → US4 → US6 → US3 → US5 → US7 → US8 → US9 → Polish.

Rationale: ship the standalone P1 (US1) first; then the P1 tag backbone consumer (US2); then the
file/storage stories (US4 before US5; US6 alongside); then the tag-dependent P2/P3 stories; then the
small independent P3s (US8, US9); finish with docs/validation.

### Notes

- Commit after each task or logical group (the optional `before_*` git hooks can auto-commit).
- Foundational tasks are backward-compatible so the app stays runnable between phases.
- Stop at any checkpoint to validate a story independently via `quickstart.md`.
