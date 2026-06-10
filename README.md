# 🔊 Echoquize — Self-Hosted Text-to-Speech Studio

Turn text into downloadable speech with the OpenAI TTS API, and keep every generation in a
persistent, browsable library. Echoquize is a single-user web app you run on your own
infrastructure: metadata lives in SQLite, audio on a swappable storage backend, and the whole thing
ships as a multi-stage Docker image.

## Features

- **Generate & download** — enter text, pick a voice / model / format / speed, generate, preview
  inline, and download the file. Every generation is saved.
- **Batch queue** — queue multiple texts and generate them all into a single zip.
- **Persistent library** — browse, paginate, and filter past generations; preview, delete one, or
  bulk-clean by date/voice. Data survives restarts and redeploys.
- **Audio tags** — set ID3/Vorbis/Opus metadata (title, artist, album, comment, genre, year) before
  generating or edit it later; unsupported formats are skipped gracefully.
- **Self-host friendly** — 12-factor config from the environment, optional single-owner login, and
  durable persistence on a host-visible bind mount.
- **Swappable storage** — local disk by default; S3 and Google Drive are ready-to-wire backends
  selected purely by config, with no change to the rest of the app.

## Stack

Python 3.12 (managed by [uv](https://docs.astral.sh/uv/)) · [Gradio](https://www.gradio.app/) 6.x ·
OpenAI SDK 2.x · [mutagen](https://mutagen.readthedocs.io/) · SQLite (stdlib) ·
Docker (multi-stage uv build) + Compose.

---

## Quick start (local dev)

**Prerequisites:** uv 0.9+, an OpenAI API key with TTS access. (`just` and Docker are optional.)

```bash
git clone https://github.com/PeterOnCode/echoquize.git
cd echoquize

uv sync                       # install locked dependencies into .venv
cp .env.example .env          # then edit .env and set OPENAI_API_KEY=sk-...
uv run app.py                 # serve the UI at http://localhost:7860
```

A missing `OPENAI_API_KEY` makes the app **fail fast at startup** with a clear message — never a
confusing mid-request error.

### With `just` (optional task runner)

This repo ships a [`justfile`](./justfile). Run `just` with no args to list every recipe.

```bash
just install        # uv sync
just env            # create .env from the template (never overwrites an existing one)
just run            # serve the UI  (aliases: just dev / just serve)
just verify         # offline smoke checks (storage factory, DB schema, tag error path)
```

---

## Configuration

Every runtime knob is read from the environment (12-factor), so one built image runs unchanged
locally, in Docker, and on a VPS. Copy `.env.example` to `.env` and fill it in.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **yes** | — | OpenAI key with TTS access. App fails fast at startup if unset. |
| `AUDIO_DIR` | no | `./audio` | Where audio files are written (under `YYYY/MM/`). |
| `DB_PATH` | no | `./echoquize.db` | SQLite database file. |
| `HOST` | no | `0.0.0.0` | Bind address. Keep `0.0.0.0` in a container. |
| `PORT` | no | `7860` | Port the UI serves on. |
| `STORAGE_BACKEND` | no | `local` | `local` \| `s3` \| `gdrive`. |
| `UI_USERNAME` | no | — | Optional login username. |
| `UI_PASSWORD` | no | — | Optional login password. |

**Optional login:** authentication is enforced only when **both** `UI_USERNAME` and `UI_PASSWORD`
are set; leave both unset for open access. Setting only one logs a startup warning and stays open.

> Echoquize has no transport security of its own — run it behind localhost, a LAN/VPN, or a
> reverse proxy that terminates TLS. It is designed for private, single-user deployment.

---

## Using the app

- **Voices:** `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`,
  `shimmer`, `verse`, `marin`, `cedar`.
- **Models:** `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts` (the last one also accepts free-text voice
  *instructions*).
- **Formats:** `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`.
- **Text limit:** 4096 characters **per item** (validated before any API call; batch items are each
  checked individually, not as a combined total).

### Tag support by format

| Format | Inline preview | Embedded tags |
|--------|:--------------:|:-------------:|
| mp3 | ✅ | ✅ (ID3) |
| wav | ✅ | ✅ (ID3) |
| flac | ✅ | ✅ (Vorbis) |
| opus | ✅ | ✅ (OpusTags) |
| aac | ✅ | ❌ (skipped with a notice) |
| pcm | ❌ (download-only) | ❌ (skipped with a notice) |

---

## Docker deployment

```bash
# 1) Create the persistent data dir, owned by the container's non-root user (uid 999).
mkdir -p data && sudo chown -R 999:999 data

# 2) Build and start (audio + DB persist under ./data on the host).
docker compose up -d --build      # or: just up

curl -I localhost:7860            # → HTTP 200 once Gradio is up
```

`compose.yml` maps `${PORT:-7860}:7860`, loads secrets from `.env` via `env_file`, points
`AUDIO_DIR`/`DB_PATH` at the `./data` bind mount, and sets `restart: unless-stopped`. The runtime
image is `python:3.12-slim-bookworm`, runs as non-root **uid 999**, and contains **no uv binary and
no secrets or data** — the API key is injected at runtime, and audio/DB live only on the host mount.

```bash
docker compose down               # stop the stack — your ./data is preserved   (or: just down)
docker compose logs -f            # follow logs                                  (or: just logs)
```

> ⚠️ **Never run `docker compose down -v`.** The `-v` flag deletes the `./data` volume and destroys
> every saved generation.

---

## Storage backends

Selected by `STORAGE_BACKEND`; switching it requires **no code change**.

- **`local`** (default) — writes to `AUDIO_DIR/YYYY/MM/`.
- **`s3`** — S3-compatible object storage (AWS S3, MinIO, Cloudflare R2). Ready-to-wire stub today;
  install the optional dependency with `uv sync --extra s3` and finish `src/storage/s3.py`. Reads
  `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- **`gdrive`** — Google Drive. Ready-to-wire stub; reads `GDRIVE_FOLDER_ID`,
  `GDRIVE_CREDENTIALS_JSON`.

Unimplemented backends raise a clear `NotImplementedError`; an unknown value raises `ValueError` at
startup.

---

## Data & persistence

- Audio files: `AUDIO_DIR/YYYY/MM/<uuid>.<ext>` (in Docker: `./data/audio/...`).
- Metadata: a single `generations` SQLite table at `DB_PATH` (in Docker: `./data/echoquize.db`).
- Generations are kept **indefinitely** — there is no auto-pruning. Reclaim space via the Library
  tab's **Bulk cleanup**, or prune `./data/audio` yourself.

---

## Project structure

```text
app.py                 # Gradio entry point — builds the UI, launches the server
config.py              # Reads .env → typed config; fails fast on a missing key
src/
├── tts/client.py      # OpenAI TTS wrapper (friendly error mapping)
├── tags/writer.py     # mutagen tag writing; TagsNotSupportedError
├── storage/           # StorageBackend ABC + get_storage() factory (local/s3/gdrive)
├── db/database.py     # SQLite init + CRUD + pagination + bulk delete
└── ui/                # generate_tab.py (single + batch), library_tab.py
specs/001-echoquize-tts/   # Spec Kit artifacts: spec, plan, research, contracts, quickstart
```

## Validation

There is no automated test suite by design (this is a pragmatic single-user tool). Validation is
manual and documented in [`specs/001-echoquize-tts/quickstart.md`](./specs/001-echoquize-tts/quickstart.md),
which walks each user story (US1–US5) end to end. The offline subset runs via `just verify`.

Design and governance live under [`specs/001-echoquize-tts/`](./specs/001-echoquize-tts/) and the
project [constitution](./.specify/memory/constitution.md).

## License

No license file is present yet. Add a `LICENSE` to declare usage terms before sharing publicly.
