# Contract: config.py

Loads `.env` via python-dotenv at import and exposes typed module-level constants. (Principle III.)

## Exposed constants

| Name | Type | Default | Required | Source env var |
|------|------|---------|----------|----------------|
| `OPENAI_API_KEY` | str | — | **yes** | `OPENAI_API_KEY` |
| `AUDIO_DIR` | str | `./audio` | no | `AUDIO_DIR` |
| `DB_PATH` | str | `./echoquize.db` | no | `DB_PATH` |
| `HOST` | str | `0.0.0.0` | no | `HOST` |
| `PORT` | int | `7860` | no | `PORT` |
| `STORAGE_BACKEND` | str | `local` | no | `STORAGE_BACKEND` |
| `UI_USERNAME` | str \| None | `None` | no | `UI_USERNAME` |
| `UI_PASSWORD` | str \| None | `None` | no | `UI_PASSWORD` |

## Guarantees

- **Fail fast**: importing `config` raises `ValueError` with a clear message when `OPENAI_API_KEY` is
  missing/empty — before any UI or service starts (FR-016).
- `PORT` is coerced to `int`; a non-numeric value raises `ValueError` at import.
- `HOST` defaults to `0.0.0.0` and MUST NOT be silently forced to `127.0.0.1` (container reachability).
- No secret is logged or echoed.

## Contract tests (manual)

- `uv run python -c "import config"` with no `.env` → raises `ValueError`.
- With `.env` set → `config.OPENAI_API_KEY` returns the key; `config.PORT == 7860` by default.
