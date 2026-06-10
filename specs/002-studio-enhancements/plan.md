# Implementation Plan: TTS Studio Enhancements

**Branch**: `002-studio-enhancements` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-studio-enhancements/spec.md`

## Summary

Nine enhancements layered onto the existing Echoquize app (feature 001), grouped into three
themes:

- **Batch workflow** — populate the batch queue from an uploaded `.txt` file (one line per item),
  and make every queued item fully editable in place (text, voice, model, format, voice
  instructions, tags).
- **Metadata & files** — expand the audio tag set to the common ID3v2.4.0 frames (writing MP3/WAV
  as v2.4.0) with database persistence; name generated files from the title (transliterated slug,
  collision-safe) instead of a UUID; store audio under a day-level `YYYY/MM/DD` folder; and add a
  Library "edit details" panel that renames the file and edits the full tag set.
- **Release & visibility** — show the app version next to the title, sourced from a single
  authoritative value; and adopt `bump-my-version` so a maintainer can bump + commit + tag in one
  command.

The technical approach reuses the existing module seams: storage-layout concerns (day folder,
collision suffixing, rename) stay **inside** the `StorageBackend` so callers never build paths
(Principle I); the slug/version helpers use only the **standard library** (`unicodedata`,
`tomllib`) to avoid new runtime dependencies (Principles II/VI); tag persistence extends the
`generations` table with two additive columns via an idempotent `ALTER TABLE` migration
(Principle V); default tag values and all new knobs are read from the environment (Principle III);
and every new failure path surfaces a friendly message (Principle VII).

## Technical Context

**Language/Version**: Python 3.12 (pinned via `.python-version`, uv-managed) — unchanged.

**Primary Dependencies**: Gradio 6.x, openai SDK 2.x, python-dotenv, mutagen — unchanged at
runtime. New **dev-only** dependency: `bump-my-version` (US9). No new runtime dependency: slug
transliteration uses stdlib `unicodedata`; version reading uses stdlib `tomllib`.

**Storage**: SQLite `generations` table (additive columns `tag_track`, `tags_extra`); audio files
move from `AUDIO_DIR/YYYY/MM/` to `AUDIO_DIR/YYYY/MM/DD/`, still behind the `StorageBackend`
abstraction (now also responsible for collision-safe naming and rename).

**Testing**: Manual functional validation per user story (browser + REPL one-liners), per
Constitution Principle VI. `quickstart.md` defines the scenarios; the offline subset extends
`just verify`.

**Target Platform**: Self-hosted Linux container (Docker Compose); local dev via `uv run app.py`.
Browser UI.

**Project Type**: Single-project web application (server-side Gradio Blocks app) — unchanged.

**Performance Goals**: Single-user interactive use. File upload (US1) must stay responsive for
large files (thousands of lines parsed in-process before any API call). Per-generation latency is
still dominated by the external TTS service.

**Constraints**: Per-item text ≤ 4096 chars (validated before any API call); one image runs
unchanged across local/Docker/VPS via env config; required config validated at startup; audio + DB
persist on a host-visible bind mount; runtime container non-root uid 999; SQLite on local FS with
`check_same_thread=False` + in-process lock. New constraints: filename stem ≤ 64 chars after
slugging; collision suffixes stay within that cap; DB migration must be additive and preserve
existing rows; existing files are never renamed/moved by the generation path (US4/US6 are
new-files-only).

**Scale/Scope**: One owner/operator; low-thousands of stored generations; ephemeral per-session
batch queue; nine user stories (US1–US9).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Constitution v1.0.0 — seven principles:

| # | Principle | Gate — how this design satisfies it | Status |
|---|-----------|-------------------------------------|--------|
| I | Storage Abstraction & Backend Independence | Day-folder layout, collision-safe naming, and the new `rename()` all live **inside** `StorageBackend` implementations. Callers (UI/DB) pass a desired filename/stem and receive the actual stored path back; no module outside `src/storage/` builds `YYYY/MM/DD` paths or lists directories. The new `rename()` is added to the ABC and implemented by every backend (stubs raise `NotImplementedError`, consistent with their `save()`). | ✅ PASS |
| II | Reproducible, Pinned Builds | Only one new dependency (`bump-my-version`), added as a **dev** dependency via uv and pinned in a committed `uv.lock`. No new runtime deps (stdlib `unicodedata`/`tomllib`). `bump-my-version`'s own config keeps `[project].version` and `[tool.bumpversion].current_version` in sync. | ✅ PASS |
| III | Config-as-Environment (12-Factor) | Default tag values (US7) are read from the environment with blank fallbacks; no new **required** config (the app starts fine with none set). Version display reads project metadata, not runtime config. | ✅ PASS |
| IV | Secrets & Data Never in the Image | No change to `.dockerignore`, secrets handling, or the non-root runtime user. New tag/default-tag values are user/operator data, not baked in. | ✅ PASS |
| V | Durable Persistence | Schema change is **additive** (`ALTER TABLE ADD COLUMN`, guarded by `PRAGMA table_info`), preserving all existing rows. Library rename updates the DB path in the same operation as the on-disk move. No Docker volume or teardown changes. | ✅ PASS |
| VI | Pragmatic Single-User Scope | No speculative complexity: slug/version use stdlib (no `unidecode`); custom/multi-value tags live in one `tags_extra` JSON column (no child table); per-row queue editing and Library "edit details" reuse the existing select-row → edit-panel pattern; no test suite added. `bump-my-version` is a justified dev tool replacing error-prone manual edits, requested explicitly. | ✅ PASS |
| VII | Graceful, User-Facing Error Handling | New failure paths all degrade gracefully: upload summary (added/skipped/rejected) and per-line over-length messages; rename collision auto-suffix and empty/un-sluggable name rejection with the original kept; tag-skip notices for AAC/PCM and for FLAC/Opus frames with no equivalent; version omitted if undeterminable; invalid default-tag config → blank field, app still starts. | ✅ PASS |

**Initial gate result**: PASS — no violations. Principle I is the highest-risk area and is the
explicit subject of research decisions R2–R3 and the storage-backend contract.

**Post-design re-check (after Phase 1)**: PASS — the data model, contracts, and quickstart preserve
every gate above. The only abstraction added beyond the simplest design is the `rename()` method on
the existing `StorageBackend` ABC, which is **required** by Principle I (renaming is a storage
operation and callers must not manipulate paths), not speculative.

## Project Structure

### Documentation (this feature)

```text
specs/002-studio-enhancements/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification (/speckit-specify)
├── research.md          # Phase 0 — resolved technical decisions R1–R11
├── data-model.md        # Phase 1 — extended entities, schema, migration, validation
├── quickstart.md        # Phase 1 — per-story validation guide
├── contracts/           # Phase 1 — module interface contracts (deltas vs feature 001)
│   ├── README.md
│   ├── naming.md
│   ├── storage-backend.md
│   ├── tag-writer.md
│   ├── database.md
│   ├── config.md
│   ├── version.md
│   └── ui-contract.md
└── checklists/
    └── requirements.md  # Spec-quality gate (/speckit-specify)
```

### Source Code (repository root)

```text
echoquize/
├── app.py                      # + version shown next to the title (US8)
├── config.py                   # + DEFAULT_TAG_* env reads (US7)
├── pyproject.toml              # + [tool.bumpversion]; + bump-my-version dev dep (US6/US9)
├── uv.lock                     # regenerated/committed after adding the dev dep (Principle II)
├── justfile                    # + bump recipes (bump-patch/minor/major) (US6)
└── src/
    ├── naming.py               # NEW — title → slug stem (US3/US4), stdlib unicodedata
    ├── version.py              # NEW — read [project].version (US8), stdlib tomllib
    ├── tts/client.py           # unchanged
    ├── tags/writer.py          # expanded tag set + explicit ID3v2.4.0 + new frames (US2)
    ├── storage/
    │   ├── base.py             # + rename(); save() now collision-safe (US3/US4/US5)
    │   ├── local.py            # YYYY/MM/DD layout + collision suffix + rename (US3/US4/US5)
    │   ├── s3.py               # rename() stub raises NotImplementedError
    │   └── gdrive.py           # rename() stub raises NotImplementedError
    ├── db/database.py          # + tag_track/tags_extra columns + migration + update_file_path (US2/US5)
    └── ui/
        ├── generate_tab.py     # file upload (US1), per-row edit panel (US3), expanded + default tags (US2/US7/US9), slug filename (US4)
        └── library_tab.py      # "edit details" panel: rename + expanded tags (US5/US8 not here)
```

**Structure Decision**: Single-project web application — unchanged from feature 001. Two small new
helper modules (`src/naming.py`, `src/version.py`) are added because their logic is shared across
call sites (generation, batch, Library rename / version display) and is pure/standalone, which
keeps it out of the UI and easy to validate in isolation. Everything else is a delta to existing
modules along their current seams.

## Complexity Tracking

> No constitution violations — this table is intentionally empty.

All seven principle gates pass without justification. The single new abstraction —
`StorageBackend.rename()` — is mandated by Principle I (storage owns path manipulation), exercised
by the default `LocalStorage`, and stubbed consistently by the optional backends. The two new
helper modules and the one JSON column are the simplest options that satisfy the requirements
without a heavier structure (no transliteration library, no child tables, no settings store).
