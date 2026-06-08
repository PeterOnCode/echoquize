# Implementation Plan: Echoquize — Self-Hosted Text-to-Speech Studio

**Branch**: `001-echoquize-tts` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-echoquize-tts/spec.md`

## Summary

Echoquize is a self-hosted web app that turns text into downloadable speech via a cloud TTS service,
saving every generation to a persistent library (metadata in SQLite, audio on a storage backend).
Users generate single or batched audio, browse/paginate/filter and bulk-clean a library, and edit
ID3/Vorbis-style metadata tags. The app is packaged as a multi-stage uv Docker image and run via
Compose with audio + DB on a bind-mounted volume so data survives rebuilds. Storage is abstracted
behind an ABC + factory so local disk can later be swapped for S3 or Google Drive with no change to
TTS, UI, or DB code.

## Technical Context

**Language/Version**: Python 3.12 (pinned via `.python-version`, interpreter auto-managed by uv)

**Primary Dependencies**: Gradio 6.x (Blocks UI), openai SDK 2.x (TTS), python-dotenv (config),
mutagen (audio tags); uv for dependency management and the Docker build

**Storage**: SQLite (stdlib `sqlite3`) for the `generations` metadata table; local filesystem for
audio files under `AUDIO_DIR/YYYY/MM/`, accessed through a `StorageBackend` abstraction

**Testing**: Manual functional validation per increment (browser + REPL one-liners), per
Constitution Principle VI (no automated suite mandated). `quickstart.md` defines the validation
scenarios. pytest may be added later only if complexity grows.

**Target Platform**: Self-hosted Linux container (Docker Compose) for production; local dev on
macOS/Linux via `uv run app.py`. UI is browser-based; audio playback is client-side.

**Project Type**: Single-project web application (server-side Gradio Blocks app, no separate
frontend build)

**Performance Goals**: Single-user interactive use. Per-generation latency is dominated by the
external TTS service (≈5–15s for text approaching 4096 chars). Library renders a page of results
without noticeable delay at ≥1,000 stored generations (SC-009).

**Constraints**: Per-item text ≤ 4096 chars (validated before any API call); one image runs
unchanged across local/Docker/VPS via env config; required config validated at startup (fail fast);
audio + DB persist on a host-visible bind mount; no secrets or data baked into the image; runtime
container runs as non-root uid 999; SQLite on a local filesystem with `check_same_thread=False` plus
an in-process threading lock; `instructions` param only sent for `gpt-4o-mini-tts`.

**Scale/Scope**: One owner/operator; low-thousands of stored generations browsed via
pagination + filtering; ephemeral per-session batch queue; five user stories (US1–US5) mapping to
the five sprints.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Constitution v1.0.0 — seven principles. Each maps to a design gate:

| # | Principle | Gate — how this design satisfies it | Status |
|---|-----------|-------------------------------------|--------|
| I | Storage Abstraction & Backend Independence | All audio I/O goes through `StorageBackend` ABC + `get_storage()` factory (`src/storage/`). TTS/UI/DB never import a concrete backend or build filesystem paths. | ✅ PASS |
| II | Reproducible, Pinned Builds | `pyproject.toml` + committed `uv.lock`; `uv sync --frozen` in Docker; upgrades only via deliberate `uv lock --upgrade`; builder + runtime images both pinned to Python 3.12 = `.python-version`. | ✅ PASS |
| III | Config-as-Environment (12-Factor) | `config.py` reads every knob from env (`OPENAI_API_KEY`, `AUDIO_DIR`, `DB_PATH`, `HOST`, `PORT`, `STORAGE_BACKEND`, `UI_USERNAME`/`UI_PASSWORD`); raises `ValueError` at import when `OPENAI_API_KEY` is missing. | ✅ PASS |
| IV | Secrets & Data Never in the Image | `.dockerignore` excludes `.env`, `audio/`, `data/`, `echoquize.db`, `.venv/`, `.git/`; secrets injected at runtime via Compose `env_file`; runtime user is non-root uid 999. | ✅ PASS |
| V | Durable Persistence | `./data` bind mount holds audio + SQLite; `check_same_thread=False` + threading lock; teardown preserves data; `down -v` flagged as destructive (never run without confirmation). | ✅ PASS |
| VI | Pragmatic Single-User Scope | No automated test suite; manual per-increment validation in `quickstart.md`; no queues/multi-user/scaling added speculatively. | ✅ PASS |
| VII | Graceful, User-Facing Error Handling | TTS client catches `openai.RateLimitError`/`AuthenticationError`/`APIError`; UI surfaces friendly status; PCM → download-only + notice; PCM/raw-AAC tagging skipped with notice via `TagsNotSupportedError`. | ✅ PASS |

**Initial gate result**: PASS — no violations. **Post-design re-check (after Phase 1)**: PASS — the
data model, contracts, and quickstart preserve every gate above; no new complexity introduced.

## Project Structure

### Documentation (this feature)

```text
specs/001-echoquize-tts/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature specification (/speckit-specify + /speckit-clarify)
├── research.md          # Phase 0 — resolved technical decisions
├── data-model.md        # Phase 1 — entities, schema, validation rules
├── quickstart.md        # Phase 1 — runnable per-story validation guide
├── contracts/           # Phase 1 — internal module interface contracts
│   ├── README.md
│   ├── config.md
│   ├── tts-client.md
│   ├── storage-backend.md
│   ├── database.md
│   ├── tag-writer.md
│   └── ui-contract.md
└── checklists/
    ├── requirements.md  # Spec-quality gate (/speckit-specify)
    └── readiness.md     # Author pre-plan requirements-quality review (/speckit-checklist)
```

### Source Code (repository root)

```text
echoquize/
├── app.py                      # Gradio entry point — builds Blocks, demo.launch()
├── config.py                   # Reads .env → typed config constants; fail-fast on missing key
├── pyproject.toml              # Project metadata + dependencies (uv-managed)
├── uv.lock                     # Locked dependency versions (committed)
├── .python-version             # Interpreter pin (3.12)
├── Dockerfile                  # Multi-stage uv build → slim non-root runtime
├── .dockerignore               # Keeps secrets/data/bloat out of image layers
├── compose.yml                 # Port map, env_file, ./data bind mount, restart policy
├── .env.example                # Documented config template (committed)
├── .gitignore
└── src/
    ├── tts/client.py           # generate_speech(text, model, voice, format, speed, instructions)
    ├── tags/writer.py          # write_tags(path, fmt, tags); TagsNotSupportedError
    ├── storage/
    │   ├── __init__.py         # get_storage() factory (reads STORAGE_BACKEND)
    │   ├── base.py             # StorageBackend ABC: save/delete/get_url
    │   ├── local.py            # LocalStorage (default)
    │   ├── s3.py               # S3Storage stub (optional boto3 extra)
    │   └── gdrive.py           # GDriveStorage stub
    ├── db/database.py          # SQLite init + CRUD + pagination + bulk delete (threading lock)
    └── ui/
        ├── generate_tab.py     # Single + batch generation, tags accordion
        └── library_tab.py      # Paginated/filterable library, bulk cleanup, tag editor
```

**Structure Decision**: Single-project web application. The Gradio Blocks app (`app.py`) composes two
UI tabs (`src/ui/`) over four internal service modules (`tts`, `tags`, `storage`, `db`). The storage
package is the one deliberate abstraction (Constitution Principle I); everything else is direct,
flat, and single-purpose to honor Principle VI (pragmatic scope).

## Complexity Tracking

> No constitution violations — this table is intentionally empty.

All seven principle gates pass without justification. The only abstraction beyond the simplest
possible design is the `StorageBackend` ABC + factory, which is **required** by Principle I (not
speculative): it is the mandated extension point for S3/GDrive and is exercised by the default
`LocalStorage` from day one.
