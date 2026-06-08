# Plan: Echoquize — Python + Gradio TTS Web App

**Generated**: 2026-06-08
**Estimated Complexity**: Medium

## Overview

Echoquize is a self-hosted web application that converts text to speech via the OpenAI TTS API. Users enter text, pick a voice/model/format/speed, generate audio, and download it. A persistent library (SQLite + local filesystem) stores every generation. The storage layer is abstracted so filesystem can be swapped for S3 or Google Drive later. The app is packaged as a Docker image (multi-stage uv build) and run via Docker Compose, with audio files and the SQLite DB on a mounted volume so they persist across container rebuilds.

Stack: Python 3.11+ (managed by **uv**), Gradio 6.x (Blocks layout), openai Python SDK 2.x, SQLite (stdlib), python-dotenv, mutagen (audio tag writing). Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`; the project resolves to the **newest** compatible releases (verified 2026-06-08: gradio 6.17.3, openai 2.41.0, python-dotenv 1.2.2, mutagen 1.47.0).

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.9+ — Python/dependency manager for local dev and inside the Docker build (installed: uv 0.9.9)
- Docker Engine 24+ and Docker Compose v2 — the container runtime used to run/deploy the app (uv runs *inside* the image build; not required on the host to run the container)
- Python 3.11+ (uv auto-installs a suitable interpreter; pin via `.python-version`)
- OpenAI API key with TTS access
- Git (repo already initialized)

---

## File Structure

```
echoquize/
├── app.py                      # Gradio entry point — launches the UI
├── config.py                   # Reads .env, exposes typed config constants
├── pyproject.toml              # Project metadata + dependencies (uv-managed)
├── uv.lock                     # Locked dependency versions (committed)
├── .python-version             # Interpreter pin for uv (committed)
├── Dockerfile                  # Multi-stage uv build → slim runtime (Task 4.5)
├── .dockerignore               # Keeps .env, audio/, data/, .venv, .git out of the image
├── compose.yml                 # Docker Compose: port map, env_file, persistent volume (Task 4.6)
├── .env.example                # Template (committed)
├── .env                        # Actual secrets (gitignored)
├── .gitignore
├── src/
│   ├── tts/
│   │   └── client.py           # OpenAI TTS wrapper — generate_speech()
│   ├── tags/
│   │   └── writer.py           # mutagen tag writing — write_tags(path, format, tags)
│   ├── storage/
│   │   ├── base.py             # Abstract StorageBackend ABC
│   │   └── local.py            # LocalStorage: saves to audio/ directory
│   ├── db/
│   │   └── database.py         # SQLite init, CRUD for generations table
│   └── ui/
│       ├── generate_tab.py     # Single + batch generation tab
│       └── library_tab.py      # Persistent library browse/filter tab
├── audio/                      # Local-dev default audio dir (gitignored)
│   └── YYYY/MM/                # Subdirectory by year/month
├── echoquize.db                # Local-dev default SQLite DB (gitignored)
└── data/                       # Docker bind-mount: container writes audio+DB here (gitignored)
    ├── audio/                  #   via AUDIO_DIR=/app/data/audio
    └── echoquize.db            #   via DB_PATH=/app/data/echoquize.db
```

---

## Sprint 1: Project Foundation + Single Generation

**Goal**: Run `uv run app.py`, open the UI, enter text, generate audio, download the file.

**Demo/Validation**:
- `uv run app.py` launches Gradio UI at `http://localhost:7860`
- Enter any text, click Generate, audio player appears, file downloads
- Audio file written to `audio/YYYY/MM/<uuid>.mp3`

### Task 1.1: Project scaffold (uv)

- **Location**: `/`, `src/`, `audio/`, `.gitignore`, `pyproject.toml`, `.python-version`
- **Description**:
  1. Initialize the project: `uv init --app --python 3.12` (creates `pyproject.toml`, `.python-version`, `.gitignore` baseline). Using 3.12 for the broadest wheel coverage — see Gotcha 14 before choosing 3.14.
  2. Add runtime dependencies, resolving to newest: `uv add gradio openai python-dotenv mutagen`. This writes pinned lower bounds into `pyproject.toml` and creates `uv.lock`.
  3. Create the package directory tree with empty `__init__.py` files: `src/tts/`, `src/tags/`, `src/storage/`, `src/db/`, `src/ui/`.
  4. Extend `.gitignore` to exclude `.env`, `audio/`, `echoquize.db`, `.venv/`, `__pycache__/`. (Commit `uv.lock` — do NOT ignore it.)
- **Acceptance Criteria**:
  - `pyproject.toml` lists gradio (≥6), openai (≥2), python-dotenv, mutagen; `uv.lock` exists
  - `ls src/tts src/tags src/storage src/db src/ui` all exist
  - `.gitignore` excludes `.env`, `audio/`, `.venv/`; does NOT exclude `uv.lock`
- **Validation**: `uv run python -c "import gradio, openai, dotenv, mutagen; print(gradio.__version__, openai.__version__)"` prints 6.x and 2.x after `uv sync`

### Task 1.2: Config module

- **Location**: `config.py`, `.env.example`
- **Description**: Load env vars with `python-dotenv`. Expose: `OPENAI_API_KEY`, `AUDIO_DIR` (default `./audio`), `DB_PATH` (default `./echoquize.db`), `HOST` (default `0.0.0.0`), `PORT` (default `7860`). Raise `ValueError` at startup if `OPENAI_API_KEY` is missing.
- **Acceptance Criteria**:
  - `uv run python -c "import config"` raises `ValueError` without `.env`
  - With `.env` set, `config.OPENAI_API_KEY` returns the key
- **Validation**: Manual test with and without `.env`

### Task 1.3: SQLite database module

- **Location**: `src/db/database.py`
- **Description**: On import, create `echoquize.db` if it doesn't exist. Define and create `generations` table:
  ```sql
  CREATE TABLE IF NOT EXISTS generations (
    id          TEXT PRIMARY KEY,        -- UUID
    text_input  TEXT NOT NULL,
    voice       TEXT NOT NULL,
    model       TEXT NOT NULL,
    format      TEXT NOT NULL,
    speed       REAL NOT NULL,
    file_path   TEXT NOT NULL,
    file_size   INTEGER,
    created_at  TEXT NOT NULL,           -- ISO8601
    tag_title   TEXT,
    tag_artist  TEXT,
    tag_album   TEXT,
    tag_comment TEXT,
    tag_genre   TEXT,
    tag_year    TEXT
  )
  ```
  Expose functions: `insert_generation(...)`, `list_generations(limit, offset)`, `get_generation(id)`, `delete_generation(id)`, `update_tags(id, tags: dict)`.
- **Acceptance Criteria**:
  - `uv run python -c "from src.db.database import init_db; init_db()"` creates DB with correct schema
- **Validation**: `sqlite3 echoquize.db ".schema"` shows the table

### Task 1.4: Local storage backend

- **Location**: `src/storage/base.py`, `src/storage/local.py`
- **Description**: Define `StorageBackend` ABC with `save(data: bytes, filename: str) -> str` (returns file path) and `delete(path: str) -> None`. Implement `LocalStorage`: stores files under `audio/YYYY/MM/` subdirectories, creates dirs as needed.
- **Acceptance Criteria**:
  - `LocalStorage().save(b"test", "test.mp3")` creates file and returns its path
- **Validation**: Unit-test manually in REPL

### Task 1.5: OpenAI TTS client wrapper

- **Location**: `src/tts/client.py`
- **Description**: Expose `generate_speech(text, model, voice, format, speed) -> bytes`. Use `client.audio.speech.with_streaming_response.create(...)` + `response.read()` to get bytes (this streaming-context API is unchanged in openai SDK 2.x). Initialize `OpenAI(api_key=config.OPENAI_API_KEY)`. Validate `len(text) <= 4096`.
  
  Supported values (from API docs):
  - **Models**: `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`
  - **Voices**: `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse`, `marin`, `cedar`
  - **Formats**: `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`
  - **Speed**: 0.25–4.0
  
  Note: `instructions` param only works with `gpt-4o-mini-tts`. Include it as optional param, ignored for other models.
- **Acceptance Criteria**:
  - Returns non-empty `bytes` for a short test string
- **Validation**: `uv run python -c "from src.tts.client import generate_speech; d = generate_speech('hello', 'tts-1', 'alloy', 'mp3', 1.0); print(len(d), 'bytes')"`

### Task 1.6: Single-generation Gradio UI tab

- **Location**: `src/ui/generate_tab.py`, `app.py`
- **Description**: Build a `gr.Blocks()` layout with one tab ("Generate"):
  - `gr.Textbox(label="Text", lines=5, max_lines=20, placeholder="Enter text to convert...", max_length=4096)`
  - `gr.Dropdown(label="Voice", choices=[...13 voices...], value="alloy")`
  - `gr.Dropdown(label="Model", choices=["tts-1", "tts-1-hd", "gpt-4o-mini-tts"], value="tts-1")`
  - `gr.Dropdown(label="Format", choices=["mp3", "opus", "aac", "flac", "wav", "pcm"], value="mp3")`
  - `gr.Slider(label="Speed", minimum=0.25, maximum=4.0, step=0.05, value=1.0)`
  - `gr.Textbox(label="Voice Instructions (gpt-4o-mini-tts only)", visible=True)` — shown/hidden by model selection
  - `gr.Button("Generate")`
  - `gr.Audio(label="Preview", type="filepath")` — plays result inline
  - `gr.File(label="Download")` — download link
  - `gr.Textbox(label="Status")` — shows errors or success info
  
  On Generate: call `generate_speech()`, save via `LocalStorage`, insert into DB, return audio path for preview + download.
- **Acceptance Criteria**:
  - UI loads, generate works, audio plays in browser, file downloads
  - Status shows file size and path on success; error message on failure
- **Validation**: Manual browser test

---

## Sprint 2: Batch Generation + Persistent Library

**Goal**: Add multiple texts in a queue, generate all at once. Browse all past generations in a library tab.

**Demo/Validation**:
- Add 3 texts with different voices, click "Generate All", all 3 audio files appear
- Switch to Library tab, see all past generations with metadata
- Delete a generation from library, confirm it disappears

### Task 2.1: Batch queue UI

- **Location**: `src/ui/generate_tab.py`
- **Description**: Add a "Batch" section below the single generator:
  - `gr.Dataframe` with columns: `#`, `Text (preview)`, `Voice`, `Model`, `Format`, `Speed` — shows queued items
  - `gr.Button("Add to Queue")` — adds current form state as a row
  - `gr.Button("Remove Selected")` — removes highlighted row
  - `gr.Button("Generate All")` — runs TTS on each queued item sequentially
  - `gr.File(label="Download All (zip)")` — zip of all generated files
  - Progress: `gr.Progress()` tracks batch completion
  
  Internal state: use `gr.State` to hold the queue list.
- **Acceptance Criteria**:
  - Can add/remove items from queue
  - "Generate All" produces one audio file per queue item
  - Zip download contains all generated files
- **Validation**: Add 2-3 items, generate all, verify zip contents

### Task 2.2: Library tab

- **Location**: `src/ui/library_tab.py`
- **Description**: Add a "Library" tab to the Gradio app:
  - `gr.Dataframe` showing columns: `ID`, `Created`, `Voice`, `Model`, `Format`, `Speed`, `Text (preview 60 chars)`, `File Size`
  - Data loaded from `list_generations()` on tab open and after each generation
  - `gr.Button("Refresh")` — reloads from DB
  - `gr.Dropdown(label="Filter by Voice")` — filters rows client-side
  - Row select → `gr.Audio` previews the selected file
  - `gr.Button("Delete Selected")` — deletes DB record + file from disk
- **Acceptance Criteria**:
  - All past generations visible after app restart (data is truly persistent)
  - Delete removes DB row and audio file
  - Voice filter narrows the list
- **Validation**: Generate a file, restart app, verify file appears in Library

---

## Sprint 3: Audio Tag Editing

**Goal**: Users can set ID3/Vorbis metadata tags at generation time and edit them later in the Library.

**Demo/Validation**:
- Fill in Title + Artist before generating; open the file in a media player and verify tags appear
- In the Library tab, select a past generation, edit its Comment, save — re-open file and verify change
- PCM format shows a clear "Tags not supported for PCM" notice (no container format)

### Task 3.1: Tag writer module

- **Location**: `src/tags/writer.py`
- **Description**: Expose `write_tags(file_path: str, fmt: str, tags: dict) -> None` using `mutagen`. Map `fmt` to the correct mutagen class:

  | Format | mutagen class | Tag style |
  |--------|--------------|-----------|
  | `mp3`  | `mutagen.easyid3.EasyID3` | ID3 (EasyID3 API) |
  | `wav`  | `mutagen.wave.WAVE` + ID3 | ID3 embedded in WAV |
  | `flac` | `mutagen.flac.FLAC` | VorbisComment |
  | `opus` | `mutagen.oggopus.OggOpus` | OpusTags |
  | `aac`  | `mutagen.mp4.MP4` | iTunes-style atoms |
  | `pcm`  | — | Raise `TagsNotSupportedError` (raw bytes, no container) |

  `tags` dict keys: `title`, `artist`, `album`, `comment`, `genre`, `year`. Skip keys with empty/None values. For EasyID3: use `date` key for year. For MP4: map to `©nam`, `©ART`, `©alb`, `©cmt`, `©gen`, `©day`.

  Define `TagsNotSupportedError(ValueError)` in this module.
- **Acceptance Criteria**:
  - `write_tags("test.mp3", "mp3", {"title": "Hello", "artist": "Echo"})` — file tags readable by VLC/iTunes
  - `write_tags("test.pcm", "pcm", {})` raises `TagsNotSupportedError`
- **Validation**: Generate an MP3, write tags, open in VLC → Info → verify title/artist shown

### Task 3.2: Tag fields in Generate tab

- **Location**: `src/ui/generate_tab.py`
- **Description**: Add a collapsible `gr.Accordion(label="Audio Tags (optional)", open=False)` section below the format/speed controls containing:
  - `gr.Textbox(label="Title")`
  - `gr.Textbox(label="Artist")`
  - `gr.Textbox(label="Album")`
  - `gr.Textbox(label="Comment")`
  - `gr.Textbox(label="Genre")`
  - `gr.Textbox(label="Year", max_lines=1)`

  On Generate: after saving the audio file, call `write_tags()` if any tag field is non-empty. If format is `pcm`, show "Tags are not supported for PCM format — skipped" in status but do not block generation. Store all tag values in DB via `insert_generation()`.
- **Acceptance Criteria**:
  - Tags accordion is hidden by default (clean UI for users who don't need it)
  - Filling Title + Artist and generating MP3 → tags present in file
  - PCM generation with tags filled shows warning but completes successfully
- **Validation**: Manual browser test — generate with tags, verify in VLC

### Task 3.3: Tag editor in Library tab

- **Location**: `src/ui/library_tab.py`
- **Description**: When a row is selected in the Library dataframe, populate a "Edit Tags" panel below it:
  - Six `gr.Textbox` fields (title, artist, album, comment, genre, year) pre-filled from DB
  - `gr.Button("Save Tags")` — calls `write_tags()` on the file + `update_tags()` in DB
  - `gr.Button("Clear Tags")` — writes empty tags to file + clears DB tag fields
  - Status textbox shows "Tags saved" or error message

  If the selected file's format is `pcm`, disable the Save Tags button and show "Tags not supported for PCM".
- **Acceptance Criteria**:
  - Select an MP3 in library → edit title → Save → open file in media player → new title shown
  - Select a PCM file → Save Tags button is disabled
  - Tags persist across app restarts (stored in DB and written to file)
- **Validation**: Edit tags on a library item, restart app, re-select item, verify fields pre-fill correctly

---

## Sprint 4: UI Polish + Production Hardening

**Goal**: App is production-ready and runs as a Docker container on a self-hosted VPS.

**Demo/Validation**:
- `docker compose up -d --build` builds the image and serves the UI on the configured port
- Audio + DB persist across `docker compose down && docker compose up` (stored on the `./data` volume)
- App runs behind a reverse proxy (nginx) without issues
- Long text (4096 chars) generates correctly
- API errors (rate limit, invalid key) show user-friendly messages

### Task 4.1: Error handling & input validation

- **Location**: `src/tts/client.py`, `src/ui/generate_tab.py`
- **Description**: Catch `openai.RateLimitError`, `openai.AuthenticationError`, `openai.APIError`. Surface as friendly status messages. Validate text is not empty and ≤ 4096 chars before API call. Add character counter to Textbox.
- **Acceptance Criteria**:
  - Empty text shows "Text is required" without calling API
  - Wrong API key shows "Invalid API key — check your .env" not a traceback
- **Validation**: Test with invalid key, empty input, 4100-char input

### Task 4.2: Voice instructions support (gpt-4o-mini-tts)

- **Location**: `src/ui/generate_tab.py`, `src/tts/client.py`
- **Description**: When model is `gpt-4o-mini-tts`, show the Voice Instructions textbox (hide for other models via `gr.update(visible=...)`). Pass `instructions` to API only when model is `gpt-4o-mini-tts`.
- **Acceptance Criteria**:
  - Instructions field visible only when gpt-4o-mini-tts selected
  - Instructions text influences audio output (test manually with style directive)
- **Validation**: Set model to `gpt-4o-mini-tts`, add instruction "Speak slowly and dramatically", verify audio

### Task 4.3: Container-ready app launch config

- **Location**: `app.py`, `.env.example`
- **Description**: Pass `server_name=config.HOST`, `server_port=config.PORT` to `demo.launch()`; set `share=False`. Keep `HOST` defaulting to `0.0.0.0` so the same build is reachable inside a container and on a VPS. Read every runtime knob (`HOST`, `PORT`, `AUDIO_DIR`, `DB_PATH`) from env so one image runs in any environment. Document these in `.env.example`. Process supervision is handled by Compose's `restart: unless-stopped` (Task 4.6); for a non-Docker host, an optional systemd unit can run `docker compose up -d` or `uv run --frozen app.py`.
- **Acceptance Criteria**:
  - `uv run app.py` (local) and the container both bind to the configured host/port
  - The app honors `AUDIO_DIR`/`DB_PATH` from env (proven by the Compose volume in Task 4.6)
- **Validation**: `uv run app.py` serves on `PORT`; `docker run -e PORT=8080 -p 8080:8080 echoquize` serves on 8080

### Task 4.4: Gradio auth (optional single-user password)

- **Location**: `app.py`, `config.py`
- **Description**: If `UI_USERNAME` and `UI_PASSWORD` are set in `.env`, enable `demo.launch(auth=(config.UI_USERNAME, config.UI_PASSWORD))`. If not set, no auth (default for personal local use).
- **Acceptance Criteria**:
  - Without creds in .env: no login prompt
  - With creds: login form appears, correct credentials pass, wrong ones fail
- **Validation**: Set creds, restart app, test login

### Task 4.5: Production Dockerfile (multi-stage, uv)

- **Location**: `Dockerfile`, `.dockerignore`
- **Description**: Multi-stage build following Astral's official uv-docker pattern. Builder stage uses the uv image to install locked deps with a cache mount; runtime stage is plain `python:3.12-slim-bookworm` (no uv) running as a non-root user. No extra system packages needed — mutagen is pure Python and audio playback is browser-side, so no `ffmpeg` (add it only if server-side transcoding is introduced later). Base image Python (3.12) must match `.python-version`.

  ```dockerfile
  # ---- builder ----
  FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
  ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0
  WORKDIR /app
  RUN --mount=type=cache,target=/root/.cache/uv \
      --mount=type=bind,source=uv.lock,target=uv.lock \
      --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
      uv sync --locked --no-install-project --no-dev
  COPY . /app

  # ---- runtime ----
  FROM python:3.12-slim-bookworm
  RUN groupadd --system --gid 999 nonroot \
   && useradd  --system --gid 999 --uid 999 --create-home nonroot
  COPY --from=builder --chown=nonroot:nonroot /app /app
  ENV PATH="/app/.venv/bin:$PATH"
  WORKDIR /app
  USER nonroot
  EXPOSE 7860
  CMD ["python", "app.py"]
  ```

  `.dockerignore` (prevents secrets/data/bloat from entering image layers):
  ```
  .venv/
  .git/
  .gitignore
  audio/
  data/
  echoquize.db
  .env
  __pycache__/
  *.pyc
  context/
  *.md
  ```
- **Acceptance Criteria**:
  - `docker build -t echoquize:latest .` succeeds
  - Final image runs as uid 999 and contains no `uv` binary (multi-stage)
  - `.env`, `audio/`, `data/` are absent from the image
- **Validation**: `docker run --rm -e OPENAI_API_KEY=sk-... -p 7860:7860 echoquize:latest` → UI reachable at `http://localhost:7860`

### Task 4.6: Docker Compose with persistent volumes

- **Location**: `compose.yml`, `.env.example`
- **Description**: Compose service builds the image, maps the port, loads secrets via `env_file`, points `AUDIO_DIR`/`DB_PATH` at a bind-mounted `./data` dir so audio + DB persist across rebuilds and stay visible on the host filesystem (matching the "audio saved on the filesystem" requirement). `restart: unless-stopped` supervises the process.

  ```yaml
  # compose.yml
  services:
    echoquize:
      build: .
      image: echoquize:latest
      ports:
        - "${PORT:-7860}:7860"
      env_file:
        - .env                 # OPENAI_API_KEY, optional UI_USERNAME/UI_PASSWORD
      environment:
        HOST: 0.0.0.0
        PORT: "7860"
        AUDIO_DIR: /app/data/audio
        DB_PATH: /app/data/echoquize.db
      volumes:
        - ./data:/app/data
      restart: unless-stopped
  ```

  Before first run, create the volume dir owned by the container's non-root user (see Gotcha 17): `mkdir -p data && sudo chown -R 999:999 data`.
- **Acceptance Criteria**:
  - `docker compose up -d --build` serves the app; `curl -I localhost:7860` returns HTTP 200
  - After generating a file, `docker compose down && docker compose up -d` → file still appears in Library
  - Generated files are visible on the host under `./data/audio/`
- **Validation**: Full down/up cycle preserves the Library; `ls ./data/audio` on the host shows the audio files

---

## Sprint 5: Storage Abstraction (Future-proofing)

**Goal**: Storage backend is swappable. Local works now; S3 and GDrive stubs are ready for wiring.

**Demo/Validation**:
- `LocalStorage` works as before
- S3Storage and GDriveStorage exist as stubs that raise `NotImplementedError` with clear messages

### Task 5.1: Storage ABC + factory

- **Location**: `src/storage/base.py`, `src/storage/local.py`
- **Description**: Solidify the `StorageBackend` ABC with `save()`, `delete()`, `get_url(path) -> str` methods. Add `get_storage() -> StorageBackend` factory in `src/storage/__init__.py` that reads `STORAGE_BACKEND` env var (`local`, `s3`, `gdrive`) and returns the right implementation.
- **Acceptance Criteria**:
  - `STORAGE_BACKEND=local` (default) returns `LocalStorage`
  - Unknown value raises `ValueError`
- **Validation**: Test factory with env var set/unset

### Task 5.2: S3-compatible storage stub

- **Location**: `src/storage/s3.py`
- **Description**: Implement `S3Storage(StorageBackend)`. Constructor reads `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` from env. `save()` uploads via `boto3`. `delete()` removes object. `get_url()` returns presigned URL. Add `boto3` as an optional dependency via `uv add --optional s3 boto3` (creates `[project.optional-dependencies] s3 = ["boto3>=1.43"]` in `pyproject.toml`); install on demand with `uv sync --extra s3`.
- **Acceptance Criteria**:
  - Class instantiates without error when env vars present
  - Stub raises `NotImplementedError` with message if boto3 not installed
- **Validation**: Unit test with mocked boto3

### Task 5.3: Google Drive storage stub

- **Location**: `src/storage/gdrive.py`
- **Description**: Implement `GDriveStorage(StorageBackend)` stub. Constructor reads `GDRIVE_FOLDER_ID`, `GDRIVE_CREDENTIALS_JSON` from env. `save()` and `delete()` raise `NotImplementedError("Google Drive storage not yet implemented")` with setup instructions. Leaves clear extension point for Sprint 5.
- **Acceptance Criteria**:
  - File exists with correct class structure
  - Import does not crash even without google-api-python-client installed

---

## Testing Strategy

| Sprint | How to verify |
|--------|--------------|
| 1 | Manual browser test: generate + download a single file |
| 2 | Manual: batch 3 items, download zip, restart app, verify library shows all |
| 3 | Generate MP3 with tags → verify in VLC; edit tag in library → verify persists after restart |
| 4 | Edge cases (empty text, bad API key, 4096-char input); `docker compose up -d --build` serves the UI and a down/up cycle preserves the Library from `./data` |
| 5 | `uv run python` REPL: instantiate each storage class, call `get_storage()` with each env value |

No automated test suite in scope — this is a personal tool. Add pytest later if complexity grows.

---

## Potential Risks & Gotchas

1. **Gradio `gr.State` for batch queue**: State is per-user-session in Gradio. If app is restarted mid-session, queue is lost. This is acceptable — queue is ephemeral, library is persistent.

2. **`pcm` format has no audio player**: PCM is raw bytes with no container. Gradio's `gr.Audio` won't play it inline. Plan: for `pcm` format, skip the audio preview, offer download only. Show a note in the UI.

3. **4096-char limit is per API call**: Batch items are also each limited to 4096 chars. Validate per-item, not total.

4. **File storage on VPS**: `audio/` directory can grow large. Add a note in docs to periodically clean old files or set up a cron job. Storage abstraction (Sprint 4) is the real solution.

5. **`gpt-4o-mini-tts` instructions**: The API docs confirm `instructions` only works with `gpt-4o-mini-tts`. For `tts-1`/`tts-1-hd`, passing it has no effect but doesn't error — we should silently omit it to avoid confusion.

6. **Streaming vs non-streaming**: We use `with_streaming_response.create()` + `response.read()`. For very long texts near 4096 chars, generation can take 5-15 seconds. Gradio will show the button as loading — no timeout issues expected, but add a UI indicator.

7. **SQLite on VPS**: SQLite has no concurrent write protection if multiple browser tabs trigger simultaneous generations. At personal single-user scale this is fine. Add `check_same_thread=False` and a threading lock in `database.py` as a precaution.

8. **`opus` and `aac` format compatibility**: Some browsers can't play these inline. Use `gr.Audio` with `type="filepath"` which lets the browser decide — it will still be downloadable even if preview fails.

9. **mutagen and new MP3 files**: `EasyID3` fails with `mutagen.id3.ID3NoHeaderError` on files that have no existing ID3 header. Use `EasyID3.save()` after `EasyID3()` raises the error — the correct pattern is `try: tags = EasyID3(path) except ID3NoHeaderError: tags = mutagen.File(path, easy=True); tags.add_tags()`.

10. **WAV tag support is limited**: mutagen writes ID3 into WAV files but many media players (including Windows Media Player) ignore or strip WAV ID3 tags. Document this limitation in the UI tooltip for WAV format.

11. **Tag sync between file and DB**: If a user manually edits a file outside the app, the DB tags will be stale. Tags in DB are the source of truth for the UI only — the file is authoritative for external playback. No sync needed, but note this in docs.

12. **AAC format is usually `.m4a` container**: The OpenAI API returns AAC audio in an ADTS stream, not an M4A/MP4 container. mutagen's `MP4` class requires an M4A container — it will fail on raw AAC. Plan: for `aac` format, skip tag writing and show "Tags not supported for AAC (raw ADTS stream)" in the UI.

13. **Gradio 6 vs the reference repo**: leokwsw/OpenAI-TTS-Gradio targets an older Gradio (3.x/4.x). Gradio 6 keeps every component used here (Blocks, Dropdown, Slider, Audio, File, Dataframe, Accordion, State, Progress, DownloadData) but some kwargs and event signatures changed across major versions. Treat the reference as a behavioral guide, not copy-paste source — and rely on `uv.lock` so a future `gradio` release can't silently break the UI. Re-fetch current Gradio docs (Context7) when wiring events.

14. **Newest packages vs newest interpreter are different choices**: "Newest packages" (gradio 6.17, openai 2.41) is the goal; the newest *interpreter* (Python 3.14, the only one on this machine) is riskier — some transitive wheels may lag. The plan pins `.python-version` to **3.12** via `uv init --python 3.12` for wheel coverage; uv auto-downloads it. Bump to 3.13/3.14 later once `uv sync` resolves cleanly on it.

15. **uv.lock must be committed**: The lockfile is what makes "newest, but reproducible" work. Commit `uv.lock`; on the VPS use `uv sync --frozen` so prod installs the exact resolved versions, not a fresh (possibly newer) resolution. Re-run `uv lock --upgrade` deliberately to pull newer releases.

16. **Gradio must bind `0.0.0.0` inside the container**: Gradio's default `server_name` is `127.0.0.1`, which is unreachable from outside the container — the app would "start" but refuse all connections. `HOST=0.0.0.0` (already the default, set explicitly in `compose.yml`) is mandatory in-container; never override it to `localhost`.

17. **Volume permissions for the non-root user**: the image runs as uid 999. A bind-mounted `./data` owned by your host user is not writable by uid 999, so the first audio write or DB create fails with `PermissionError`. Fix before first run: `mkdir -p data && sudo chown -R 999:999 data`. (A named volume sidesteps this but hides files from the host — we use a bind mount specifically because the requirement is "audio saved on the filesystem" where you can see them.)

18. **Never bake secrets or data into the image**: `.dockerignore` MUST exclude `.env`, `audio/`, `data/`, `echoquize.db`, `.venv/`, `.git/`. Otherwise the API key and local audio get copied into image layers (leak + bloat). Pass `OPENAI_API_KEY` at runtime via Compose `env_file`, never via `COPY`/`ENV` in the Dockerfile.

19. **SQLite needs a real local filesystem**: keep `./data` on the host's local disk. SQLite file locking misbehaves on some networked/overlay filesystems (NFS, certain bind setups) and can corrupt the DB. The in-process threading lock (Gotcha 7) handles concurrent tabs; the volume must still be a local FS.

20. **Base-image Python must match the lock pin**: builder (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`) and runtime (`python:3.12-slim-bookworm`) must both be 3.12 to match `.python-version` and the resolved wheels — a minor-version mismatch breaks the copied `.venv` (wrong interpreter path). If you bump the pin (Gotcha 14), bump both Dockerfile stages in lockstep.

---

## Rollback Plan

- All changes are local; no external state affected until Sprint 4 (Docker / VPS deploy)
- To rollback: `git checkout .` restores all source files
- Database and audio files are outside git — delete `echoquize.db`, `audio/`, and `data/` to reset state
- Docker: `docker compose down` stops/removes the container but **retains** the `./data` bind mount (audio + DB). Do NOT run `docker compose down -v` unless you intend to delete persistent data — confirm first
- VPS deploy: roll back to the previous image tag (`docker compose up -d` with the prior `image:`), or keep the old container running until the new one is verified
