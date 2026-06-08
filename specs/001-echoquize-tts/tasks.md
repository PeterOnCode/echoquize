---
description: "Task list for Echoquize — Self-Hosted Text-to-Speech Studio"
---

# Tasks: Echoquize — Self-Hosted Text-to-Speech Studio

**Input**: Design documents from `/specs/001-echoquize-tts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: OMITTED BY DESIGN. Per Constitution Principle VI (pragmatic single-user scope), there is
no automated test suite. Each user story ends in a **manual validation checkpoint** that runs the
matching section of `quickstart.md`. Add pytest later only if complexity grows.

**Organization**: Tasks are grouped by user story (US1–US5) so each story is an independently
testable, shippable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5; Setup/Foundational/Polish tasks carry no story label
- Every task names an exact file path

## Path Conventions

Single-project layout (see plan.md): app at repo root (`app.py`, `config.py`), service modules under
`src/` (`tts/`, `tags/`, `storage/`, `db/`, `ui/`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency lock.

- [ ] T001 Initialize the uv project at repo root with `uv init --app --python 3.12` (creates `pyproject.toml` and `.python-version` pinned to 3.12)
- [ ] T002 Add runtime dependencies with `uv add gradio openai python-dotenv mutagen` (updates `pyproject.toml`, creates `uv.lock`); commit `uv.lock`
- [ ] T003 [P] Create the package tree with empty `__init__.py` files in `src/tts/`, `src/tags/`, `src/storage/`, `src/db/`, `src/ui/`
- [ ] T004 [P] Extend `.gitignore` to exclude `.env`, `audio/`, `echoquize.db`, `.venv/`, `__pycache__/` (do NOT ignore `uv.lock`)
- [ ] T005 [P] Create `.env.example` documenting `OPENAI_API_KEY`, `AUDIO_DIR`, `DB_PATH`, `HOST`, `PORT`, `STORAGE_BACKEND`, `UI_USERNAME`, `UI_PASSWORD`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core modules every user story depends on — config, storage abstraction, DB core.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 [P] Implement `config.py` per `contracts/config.md`: load `.env` via python-dotenv, expose typed constants, raise `ValueError` if `OPENAI_API_KEY` is missing, coerce `PORT` to int
- [ ] T007 [P] Implement the `StorageBackend` ABC in `src/storage/base.py` with abstract `save(data, filename) -> str`, `delete(path)`, `get_url(path) -> str` per `contracts/storage-backend.md`
- [ ] T008 [P] Implement `src/db/database.py` core per `data-model.md`/`contracts/database.md`: `init_db()` creating the `generations` table + `idx_generations_created_at` and `idx_generations_voice`; open SQLite with `check_same_thread=False` and a module-level `threading.Lock`; implement `insert_generation(record)` (UUID4 id) and `get_generation(id)`
- [ ] T009 Implement `LocalStorage` in `src/storage/local.py` (writes under `AUDIO_DIR/YYYY/MM/`, creates dirs; tolerant `delete` of a missing file; `get_url` returns the path) — depends on T007
- [ ] T010 Implement the `get_storage()` factory in `src/storage/__init__.py` returning `LocalStorage` for `local`/default and raising `ValueError` for an unknown `STORAGE_BACKEND` — depends on T007, T009

**Checkpoint**: `uv run python -c "import config"` fails fast without `.env`; `get_storage()` returns `LocalStorage`; `init_db()` creates the schema (`sqlite3 echoquize.db ".schema"`).

---

## Phase 3: User Story 1 — Generate & download speech (Priority: P1) 🎯 MVP

**Goal**: Enter text, choose voice/model/format/speed, generate, preview inline, download the file; every generation is saved.

**Independent Test**: Open the app, enter a sentence, Generate → audio plays and a file downloads; a row + audio file exist.

- [ ] T011 [P] [US1] Implement `generate_speech(text, model, voice, format, speed, instructions=None)` in `src/tts/client.py` using `client.audio.speech.with_streaming_response.create(...)` + `response.read()`; send `instructions` only for `gpt-4o-mini-tts`; catch `openai.AuthenticationError`/`RateLimitError`/`APIError` per `contracts/tts-client.md` — depends on T006
- [ ] T012 [P] [US1] Build the single-generation Generate tab in `src/ui/generate_tab.py`: Text (≤4096) with character counter, Voice/Model/Format dropdowns, Speed slider (0.25–4.0, step 0.05), Voice-Instructions textbox visible only for `gpt-4o-mini-tts`, Generate button, `gr.Audio` preview, `gr.File` download, Status box
- [ ] T013 [US1] Wire the Generate event in `src/ui/generate_tab.py`: validate non-empty + ≤4096 → `generate_speech` → `get_storage().save` → `insert_generation` → return preview + download + status(file size); `pcm` → download-only + note; map errors to friendly status — depends on T010, T011, T012
- [ ] T014 [US1] Create `app.py`: `gr.Blocks` mounting the Generate tab, call `init_db()` at startup, `demo.launch(server_name=config.HOST, server_port=config.PORT, share=False)` — depends on T013

**Checkpoint (manual)**: Run `quickstart.md` → US1. MVP is shippable here.

---

## Phase 4: User Story 2 — Batch generation & persistent library (Priority: P2)

**Goal**: Queue multiple texts and generate all (zip download); browse a paginated/filterable library; delete single or in bulk; data persists across restarts.

**Independent Test**: Batch 3 texts → 3 files in one zip; open Library → all past generations listed, filter by voice, delete one, restart app → library still populated.

- [ ] T015 [P] [US2] Extend `src/db/database.py` with `list_generations(limit=50, offset=0, voice=None)` (ORDER BY `created_at` DESC), `count_generations(voice=None)`, `delete_generation(id)` (returns `file_path`), and `bulk_delete(voice=None, date_from=None, date_to=None)` (returns `file_paths`) per `contracts/database.md`
- [ ] T016 [US2] Add the Batch section to `src/ui/generate_tab.py`: `gr.Dataframe` queue, Add-to-Queue, Remove-Selected, Generate-All with `gr.Progress`, `gr.File` zip download; queue held in `gr.State`; validate each item ≤4096 (per item, not total) — depends on T013
- [ ] T017 [US2] Implement the Generate-All handler in `src/ui/generate_tab.py`: for each queued item `generate_speech` → `get_storage().save` → `insert_generation`, then bundle all outputs into one zip for download — depends on T016
- [ ] T018 [US2] Build the Library tab in `src/ui/library_tab.py`: paginated `gr.Dataframe` (ID, Created, Voice, Model, Format, Speed, Text preview 60 chars, File Size) via `list_generations`, Voice filter dropdown, Refresh, page controls, row-select → `gr.Audio` preview — depends on T015
- [ ] T019 [US2] Implement Library deletion in `src/ui/library_tab.py`: Delete Selected → `delete_generation` + `get_storage().delete`; Bulk cleanup (date range and/or voice) → confirmation → `bulk_delete` + remove returned files — depends on T015, T018
- [ ] T020 [US2] Mount the Library tab in `app.py` and refresh it after each generation — depends on T014, T018

**Checkpoint (manual)**: Run `quickstart.md` → US2 (including restart-persistence and ~1,000-row responsiveness).

---

## Phase 5: User Story 3 — Audio metadata tags (Priority: P3)

**Goal**: Set tags before generating or edit them later in the Library; unsupported formats handled gracefully.

**Independent Test**: Generate an mp3 with Title+Artist → tags visible in VLC; edit a tag in Library → persists after restart; pcm with tags → completes with a "skipped" notice.

- [ ] T021 [P] [US3] Implement `src/tags/writer.py`: `write_tags(path, fmt, tags)` + `TagsNotSupportedError`; map mp3→`EasyID3` (year→`date`), wav→`WAVE`+ID3, flac→`FLAC`, opus→`OggOpus`; handle `ID3NoHeaderError`; raise for `pcm`; treat `aac` as unsupported per `contracts/tag-writer.md`
- [ ] T022 [P] [US3] Add `update_tags(id, tags)` to `src/db/database.py`
- [ ] T023 [US3] Add an Audio Tags accordion (Title/Artist/Album/Comment/Genre/Year, closed by default) to `src/ui/generate_tab.py`; after saving the file, call `write_tags` when any tag is set and the format is taggable; `pcm`/`aac` → status notice but still complete; persist tag values via `insert_generation` — depends on T013, T021, T022
- [ ] T024 [US3] Add an Edit Tags panel to `src/ui/library_tab.py`: six fields pre-filled on row-select; Save Tags → `write_tags` + `update_tags`; Clear Tags → write empty + clear DB; disable Save for `pcm`/`aac` with a notice — depends on T018, T021, T022

**Checkpoint (manual)**: Run `quickstart.md` → US3.

---

## Phase 6: User Story 4 — Self-host & operate (Priority: P4)

**Goal**: Deploy via Docker Compose with config from env, optional password, and data persisting on a bind mount.

**Independent Test**: `docker compose up -d --build` → UI reachable; generate a file → `down`/`up` → file still in Library and visible under `./data/audio/`.

- [ ] T025 [US4] Add container launch config + optional auth in `app.py`: keep `server_name=config.HOST`, `server_port=config.PORT`, `share=False`; pass `auth=(config.UI_USERNAME, config.UI_PASSWORD)` only when both are set — depends on T014
- [ ] T026 [P] [US4] Write `Dockerfile`: multi-stage uv build (builder `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` running `uv sync --locked --no-dev`; runtime `python:3.12-slim-bookworm`, non-root uid 999, `CMD ["python","app.py"]`)
- [ ] T027 [P] [US4] Write `.dockerignore` excluding `.venv/`, `.git/`, `audio/`, `data/`, `echoquize.db`, `.env`, `__pycache__/`, `*.pyc`, `context/`, `*.md`
- [ ] T028 [US4] Write `compose.yml`: build `.`, ports `${PORT:-7860}:7860`, `env_file: .env`, environment `HOST=0.0.0.0`/`PORT=7860`/`AUDIO_DIR=/app/data/audio`/`DB_PATH=/app/data/echoquize.db`, volume `./data:/app/data`, `restart: unless-stopped` — depends on T026
- [ ] T029 [P] [US4] Update `.env.example` with all runtime knobs and a note to pre-create `./data` owned by uid 999 (`mkdir -p data && sudo chown -R 999:999 data`) before the first Compose run

**Checkpoint (manual)**: Run `quickstart.md` → US4 (HTTP 200, optional auth, down/up persistence, no secrets/data in image).

---

## Phase 7: User Story 5 — Swappable storage destination (Priority: P5)

**Goal**: Storage backend is selectable by config; local works, S3/GDrive are ready-to-wire stubs.

**Independent Test**: default `local` works end to end; unknown backend → `ValueError`; `s3`/`gdrive` → clear `NotImplementedError`; user-facing behavior unchanged.

- [ ] T030 [P] [US5] Add an `S3Storage(StorageBackend)` stub in `src/storage/s3.py` (reads `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`; methods raise `NotImplementedError` with a clear message; boto3 optional) per `contracts/storage-backend.md`
- [ ] T031 [P] [US5] Add a `GDriveStorage(StorageBackend)` stub in `src/storage/gdrive.py` (reads `GDRIVE_FOLDER_ID`, `GDRIVE_CREDENTIALS_JSON`; methods raise `NotImplementedError("Google Drive storage not yet implemented")`; import-safe without google libraries)
- [ ] T032 [US5] Extend `get_storage()` in `src/storage/__init__.py` to map `s3`→`S3Storage` and `gdrive`→`GDriveStorage`; add the `boto3` optional extra (`uv add --optional s3 boto3`); document the `STORAGE_BACKEND` options in `.env.example` — depends on T010, T030, T031

**Checkpoint (manual)**: Run `quickstart.md` → US5.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening across stories.

- [ ] T033 [P] Finalize friendly error/status messages across `src/ui/generate_tab.py` and `src/ui/library_tab.py` (empty text, >4096, auth failure, rate limit) so no traceback ever reaches the user (SC-004)
- [ ] T034 [P] Add format-limitation UI notices in `src/ui/`: WAV ID3 tooltip, PCM download-only + tags-skipped, AAC tags-not-supported
- [ ] T035 [P] Add a periodic storage-cleanup note to `.env.example` (and README if present) addressing storage growth
- [ ] T036 Run the full `specs/001-echoquize-tts/quickstart.md` validation (US1–US5) and tick items in `specs/001-echoquize-tts/checklists/readiness.md`
- [ ] T037 Verify constitution gates: `uv sync --frozen` resolves; built image runs as uid 999 with no `uv` binary and no `.env`/`audio/`/`data/`; a `down`/`up` cycle preserves `./data`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps; start immediately.
- **Foundational (P2)** → depends on Setup; **blocks all user stories**.
- **User Stories (P3–P7)** → all depend on Foundational. In priority order US1 → US2 → US3 → US4 → US5; US2–US5 are independently testable and could be reordered, but US1 is the MVP base.
- **Polish (P8)** → depends on the desired user stories being complete.

### Story-level dependencies

- **US1 (P1)**: Foundational only. The MVP.
- **US2 (P2)**: Foundational; extends US1's generate tab (T016/T017) and `app.py` (T020).
- **US3 (P3)**: Foundational; extends US1's generate tab (T023) and US2's library tab (T024).
- **US4 (P4)**: Foundational + US1 (`app.py` exists); deployment artifacts are otherwise standalone.
- **US5 (P5)**: Foundational; extends the storage factory (T032).

### Key blocking edges

- T001 → T002 → (T006–T010)
- T007 → T009 → T010
- T006 → T011; (T010, T011, T012) → T013 → T014
- T015 → T018 → T019; T013 → T016 → T017; (T014, T018) → T020
- T021/T022 → T023, T024
- T014 → T025; T026 → T028

---

## Parallel Execution Examples

```text
# Setup — after T001:
T003, T004, T005   (different files)

# Foundational — start of Phase 2:
T006, T007, T008   (config / storage base / db core — different files)

# US1 — after Foundational:
T011, T012         (tts client / generate-tab UI — different files), then T013 → T014

# US3 — after Foundational + US1/US2 tabs exist:
T021, T022         (tag writer / db update_tags — different files)

# US4 — deployment artifacts:
T026, T027, T029   (Dockerfile / .dockerignore / .env.example — different files)

# US5 — storage stubs:
T030, T031         (s3 / gdrive stubs — different files)
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** (`quickstart.md` US1) → demo.

### Incremental delivery

Foundation → US1 (MVP) → US2 → US3 → US4 → US5, validating each story's quickstart section before
moving on. Each story adds value without breaking the previous ones.

---

## Notes

- **No test tasks by design** (Constitution Principle VI). Validation is the manual `quickstart.md`
  checkpoint at the end of each story.
- `[P]` = different files, no dependency on an incomplete task. Tasks touching the same file
  (e.g., several US2 edits to `generate_tab.py`) are intentionally sequential.
- Commit `uv.lock`; always install with `uv sync --frozen` outside deliberate upgrades (Principle II).
- Never run `docker compose down -v` — it destroys the `./data` volume (Principle V).
- Total: 37 tasks across 8 phases.
