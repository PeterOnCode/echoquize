# Echoquize — task runner. Run `just` (no args) to list recipes.
# Requires: just (https://just.systems) and uv (https://docs.astral.sh/uv).
# Recipes auto-load .env, so config-dependent checks need it filled in (see `just env`).

set dotenv-load := true

compose := "docker compose"

# List available recipes.
default:
    @just --list

# --- Setup ----------------------------------------------------------------

# Install locked dependencies into .venv.
install:
    uv sync

# Alias for install.
sync: install

# Create .env from the template (never overwrites an existing .env).
env:
    @test -f .env && echo ".env exists — left untouched." \
        || (cp .env.example .env && echo "Created .env — edit it and set OPENAI_API_KEY.")

# Re-resolve and update uv.lock.
lock:
    uv lock

# Upgrade dependencies to the latest allowed and refresh the lock.
upgrade:
    uv sync --upgrade

# --- Run ------------------------------------------------------------------

# Serve the Gradio UI (http://localhost:$PORT, default 7860).
run:
    uv run app.py

# Alias for run.
dev: run

# Alias for run.
serve: run

# --- Validation (mirrors specs/001-echoquize-tts/quickstart.md) -----------

# Smoke check: storage backend + DB schema (needs .env with OPENAI_API_KEY).
check:
    uv run python -c "from src.storage import get_storage; from src.db.database import init_db; init_db(); print('storage:', type(get_storage()).__name__); print('db: schema ok')"

# US1: synthesize a tiny clip — proves the OpenAI key works (makes a real API call).
check-tts:
    uv run python -c "from src.tts.client import generate_speech; print(len(generate_speech('hello','tts-1','alloy','mp3',1.0)), 'bytes')"

# US3: PCM has no tag container — must raise TagsNotSupportedError. (No API key needed.)
check-tags:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python - <<'PY'
    from src.tags.writer import write_tags, TagsNotSupportedError
    try:
        write_tags("x.pcm", "pcm", {})
    except TagsNotSupportedError as exc:
        print(f"OK: pcm raises TagsNotSupportedError ({exc})")
    else:
        raise SystemExit("FAIL: pcm did not raise")
    PY

# US5: default backend resolves to LocalStorage (needs .env).
check-storage:
    uv run python -c "from src.storage import get_storage; assert type(get_storage()).__name__ == 'LocalStorage'; print('OK: default backend is LocalStorage')"

# Run the offline checks that don't hit the API.
verify: check check-tags check-storage

# --- Docker (US4 — needs Dockerfile + compose.yml from tasks T026/T028) ---

# Build and start the stack in the background.
up:
    {{compose}} up -d --build

# Stop the stack. Preserves ./data — NEVER use `down -v` (it destroys the volume).
down:
    {{compose}} down

# Rebuild image and restart.
redeploy: down up

# Follow container logs.
logs:
    {{compose}} logs -f

# Show container status.
ps:
    {{compose}} ps

# --- Housekeeping ---------------------------------------------------------

# Remove Python caches only. Does NOT touch audio/ or echoquize.db (your data).
clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete
    @echo "Cleaned Python caches (audio/ and echoquize.db left intact)."
