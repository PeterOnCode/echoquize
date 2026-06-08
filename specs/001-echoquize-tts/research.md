# Phase 0 Research: Echoquize

**Date**: 2026-06-08 | **Feature**: 001-echoquize-tts

All technical unknowns are resolved below; the spec carries **no** open `NEEDS CLARIFICATION`
markers (the three clarifications were settled in `/speckit-clarify`). Each decision lists what was
chosen, why, and the alternatives rejected. Versions verified current as of 2026-06-08.

## D1 — Interpreter version

- **Decision**: Pin Python **3.12** via `.python-version` (`uv init --python 3.12`); uv auto-downloads it.
- **Rationale**: Broadest transitive-wheel coverage. The newest interpreter on the machine (3.14) risks lagging wheels for transitive deps. Reproducible builds (Principle II) favor the safe pin.
- **Alternatives**: 3.14 (latest) — rejected for wheel-coverage risk; can bump later once `uv sync` resolves cleanly. 3.11 — works but 3.12 is the better default.

## D2 — Dependency management & reproducibility

- **Decision**: uv with `pyproject.toml` + committed `uv.lock`; production/Docker use `uv sync --frozen`; intentional upgrades via `uv lock --upgrade`.
- **Rationale**: Principle II — "newest, but reproducible." The lockfile is authoritative; frozen installs prevent silent re-resolution on the VPS.
- **Alternatives**: pip + requirements.txt (weaker locking); Poetry (heavier, not the project standard).
- **Target versions (verified 2026-06-08)**: gradio 6.17.3, openai 2.41.0, python-dotenv 1.2.2, mutagen 1.47.0.

## D3 — UI framework

- **Decision**: Gradio 6.x with `gr.Blocks()` layout, two tabs (Generate, Library).
- **Rationale**: Fastest path to a self-hosted, browser-based audio UI with built-in `gr.Audio`, `gr.File`, `gr.Dataframe`, `gr.Accordion`, `gr.State`, `gr.Progress`. Server-side, no separate frontend build (Principle VI).
- **Alternatives**: Streamlit (less control over event wiring/components); FastAPI + custom frontend (far more work for a personal tool).
- **Note**: Gradio 6 changed some kwargs/event signatures vs 3.x/4.x reference repos — treat older examples as behavioral guides only; re-check current docs when wiring events.

## D4 — TTS client integration

- **Decision**: `openai` SDK 2.x; call `client.audio.speech.with_streaming_response.create(...)` then `response.read()` to get bytes. Send `instructions` only when model is `gpt-4o-mini-tts`.
- **Rationale**: Streaming-context API returns raw audio bytes for any format; unchanged in SDK 2.x. `instructions` is ignored by `tts-1`/`tts-1-hd`, so omit it to avoid confusion.
- **Supported values**: models `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`; voices `alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar`; formats `mp3, opus, aac, flac, wav, pcm`; speed `0.25–4.0`; text ≤ 4096 chars.
- **Error handling**: catch `openai.RateLimitError`, `openai.AuthenticationError`, `openai.APIError` → friendly status (Principle VII).

## D5 — Metadata persistence (SQLite)

- **Decision**: stdlib `sqlite3`, single `generations` table; open with `check_same_thread=False` and guard writes with a module-level `threading.Lock`.
- **Rationale**: Zero-dependency, file-based, fits single-user scale and the bind-mount persistence model (Principle V). The lock covers concurrent writes from multiple browser tabs.
- **Alternatives**: Postgres (overkill, adds a service); an ORM (unnecessary for one table).
- **Constraint**: keep the DB on a real local filesystem — SQLite locking misbehaves on NFS/overlay FS.

## D6 — Pagination & filtering (clarification Q3)

- **Decision**: `list_generations(limit, offset, voice=None)` returns a page ordered by `created_at DESC`; default page size **50**; voice filter applied in SQL (`WHERE voice = ?`).
- **Rationale**: Keeps the Library responsive up to low-thousands of rows (SC-009) without loading everything; server-side filter scales better than client-side.
- **Alternatives**: load-all + client filter (degrades as history grows); full-text search/index (out of scope per clarification).

## D7 — Retention & bulk cleanup (clarification Q2)

- **Decision**: No automatic pruning. Provide manual single delete plus **bulk delete by filter** — `delete_generations(ids)` and a `bulk_delete(filter)` (by date range and/or voice) — each removing the DB row(s) **and** the backing file(s) via `StorageBackend.delete()`. Bulk delete requires explicit user confirmation in the UI.
- **Rationale**: Matches the user's chosen middle-ground retention policy; confirmation guards against accidental mass-delete (readiness CHK013).
- **Alternatives**: automatic age/size cap (rejected — adds policy the owner didn't want); manual-only (rejected by clarification).

## D8 — Storage abstraction (Principle I)

- **Decision**: `StorageBackend` ABC with `save(data, filename) -> path`, `delete(path)`, `get_url(path) -> str`. `LocalStorage` writes under `AUDIO_DIR/YYYY/MM/`. `get_storage()` factory reads `STORAGE_BACKEND` (`local` default, `s3`, `gdrive`); unknown value → `ValueError`. `S3Storage`/`GDriveStorage` are stubs (clear `NotImplementedError`).
- **Rationale**: The mandated extension point; callers depend only on the ABC, so swapping backends needs zero changes elsewhere (SC-007).
- **Alternatives**: direct filesystem calls in callers (violates Principle I).

## D9 — Audio tag writing (mutagen)

- **Decision**: `write_tags(path, fmt, tags)` maps format → mutagen class: mp3 → `EasyID3`, wav → `WAVE`+ID3, flac → `FLAC`, opus → `OggOpus`. **pcm → `TagsNotSupportedError`** (raw bytes, no container). **aac → not supported** (OpenAI returns raw ADTS, not an M4A container mutagen's `MP4` needs) → surfaced as a notice.
- **Rationale**: Pure-Python, no system deps; format reality drives which tags are writable (Principle VII handles the unsupported cases gracefully).
- **Gotcha**: new MP3s have no ID3 header — handle `ID3NoHeaderError` by creating tags then `save()`. WAV ID3 tags are ignored by some players — document in UI tooltip.

## D10 — Configuration & startup validation (Principle III)

- **Decision**: `config.py` loads `.env` via python-dotenv and exposes typed constants: `OPENAI_API_KEY` (required → `ValueError` if missing), `AUDIO_DIR` (`./audio`), `DB_PATH` (`./echoquize.db`), `HOST` (`0.0.0.0`), `PORT` (`7860`), `STORAGE_BACKEND` (`local`), optional `UI_USERNAME`/`UI_PASSWORD`.
- **Rationale**: One image runs anywhere; fail fast on missing required config.

## D11 — Access / auth & exposure model (clarification Q1)

- **Decision**: App is intended for **private** deployment (localhost/LAN/VPN/own reverse proxy). Optional single-owner auth via `demo.launch(auth=(UI_USERNAME, UI_PASSWORD))` only when both are set; **off by default**. TLS/HTTPS is the operator's responsibility (reverse proxy), not the app's.
- **Rationale**: Matches single-user scope and the clarified posture; keeps the app simple.
- **Alternatives**: built-in TLS / mandatory auth (rejected — heavier, contradicts "optional auth").

## D12 — Packaging & deployment

- **Decision**: Multi-stage Docker (Astral uv pattern): builder = `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (`uv sync --locked --no-dev`); runtime = `python:3.12-slim-bookworm`, non-root uid 999, `CMD ["python","app.py"]`. Compose maps `${PORT:-7860}:7860`, `env_file: .env`, points `AUDIO_DIR`/`DB_PATH` at `./data` bind mount, `restart: unless-stopped`.
- **Rationale**: Satisfies Principles II/IV/V. `.dockerignore` keeps secrets/data out of layers. Bind mount keeps audio host-visible (the "files on the filesystem" requirement).
- **Gotchas**: Gradio must bind `0.0.0.0` in-container; pre-create `./data` owned by uid 999 (`sudo chown -R 999:999 data`) or first write fails with `PermissionError`; builder + runtime Python must match `.python-version` in lockstep.

## D13 — Validation strategy (Principle VI)

- **Decision**: Manual functional validation per increment, scripted in `quickstart.md` (browser checks + REPL one-liners). No pytest suite in scope.
- **Rationale**: Personal single-user tool; success criteria are demonstrable by observing behavior. Add pytest later only if complexity grows.
