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

# Pull secrets from Doppler into .env (OVERWRITES .env with the dev config).
doppler-secrets-download:
    doppler secrets download --project echoquize --config dev --no-file --format env > .env

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

# Serve with Gradio hot reload — edits to app.py or src/ reload the UI live.
reload:
    uv run gradio app.py

# Alias for run.
dev: run

# Alias for run.
serve: run

# Start this, then run the "Echoquize: attach (debugpy :5678)" launch config.
# debugpy is pulled in ephemerally via --with (no change to pyproject/uv.lock).
# Append --wait-for-client after --listen to pause startup until the debugger attaches.
# Serve under a debugpy listener on :5678 for the VS Code "attach" config.
debug:
    uv run --with debugpy python -m debugpy --listen 5678 app.py

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

# US1/US4/US8: offline helpers — slugify, app_version, and the upload parser.
check-helpers:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python - <<'PY'
    import os, tempfile
    from src.naming import slugify
    from src.version import app_version

    # slugify (US4): transliterate to ASCII, lowercase, non-Latin -> empty, cap 64.
    assert slugify("Café déjà vu") == "cafe_deja_vu", slugify("Café déjà vu")
    assert slugify("日本語") == "", "non-Latin title should slug to empty"
    assert len(slugify("x" * 200)) <= 64, "stem must be capped at 64 chars"

    # app_version (US8): never raises; a str today, None only if undeterminable.
    v = app_version()
    assert v is None or isinstance(v, str), v
    print(f"OK: slugify; app_version() -> {v!r}")

    # upload parser (US1): one item per valid line, blanks skipped, long lines rejected.
    from src.tts.client import MAX_CHARS
    from src.ui.generate_tab import _parse_upload
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("first line\n\n  \nsecond line\n" + ("x" * (MAX_CHARS + 1)) + "\n")
    try:
        valid, blank, rejected = _parse_upload(path)
    finally:
        os.unlink(path)
    assert valid == ["first line", "second line"], valid
    assert blank == 2, blank
    assert rejected == [5], rejected
    print(f"OK: _parse_upload added={len(valid)} blank={blank} rejected={rejected}")
    PY

# Run the offline checks that don't hit the API.
verify: check check-tags check-storage check-helpers

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

# --- Release (US9 — bump-my-version) --------------------------------------

# Bump the patch version (0.1.0 → 0.1.1), then commit + tag. Needs a clean tree.
bump-patch:
    uv run bump-my-version bump patch

# Bump the minor version (0.1.0 → 0.2.0), then commit + tag. Needs a clean tree.
bump-minor:
    uv run bump-my-version bump minor

# Bump the major version (0.1.0 → 1.0.0), then commit + tag. Needs a clean tree.
bump-major:
    uv run bump-my-version bump major

# --- Housekeeping ---------------------------------------------------------

# Remove Python caches only. Does NOT touch audio/ or echoquize.db (your data).
clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete
    @echo "Cleaned Python caches (audio/ and echoquize.db left intact)."
