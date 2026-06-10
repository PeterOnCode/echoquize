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

The UI has two tabs: **Generate** and **Library**.

### Generate

Type or paste text, choose options, and click **Generate**. You get an inline preview (where the
format supports it), a downloadable file, and a status line with the file size. Every generation is
saved to the Library automatically.

- **Voices:** `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`,
  `shimmer`, `verse`, `marin`, `cedar`.
    - <https://www.openai.fm/>
- **Models:** `tts-1` (fast), `tts-1-hd` (higher quality), `gpt-4o-mini-tts` — the last one also
  accepts free-text **voice instructions** to steer tone/style (ignored by the other two models).
- **Formats:** `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`.
- **Speed:** `0.25`–`4.0` (`1.0` = normal).
- **Text limit:** 4096 characters **per item**, validated *before* any API call. Empty or
  over-length text is rejected with a clear message.

**Batch:** open the **Batch queue**, add several texts (each with its own voice/model/format/speed),
then **Generate all** to receive every clip in a single zip. The queue is per-session and isn't
saved — the generated files are. The 4096-character limit applies to each item, not the combined
total.

### Library

Every past generation is listed **newest-first** with its creation time, voice, model, format,
speed, a text preview, and file size. The list is **paginated** (50 per page) and stays responsive
into the low thousands of items.

- **Filter** by voice, **page** through results, and **select a row** to replay it.
- **Delete selected** removes the record *and* its audio file.
- **Bulk cleanup** removes many at once by date range and/or voice — after a confirmation checkbox.
- **Edit tags** on any taggable item; changes are written into the file and persist across restarts.

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
- A record is written only after its file is saved, so there are no orphan rows. Deleting an item
  whose file was already removed elsewhere still cleans up the record without error.
- **Concurrency:** multiple browser tabs are safe — SQLite is opened with an in-process lock, so
  simultaneous generations don't corrupt the history.
- Keep `DB_PATH` (and `./data`) on a **real local filesystem** — SQLite file locking misbehaves on
  NFS/overlay mounts.
- Generations are kept **indefinitely** — there is no auto-pruning. Reclaim space via the Library
  tab's **Bulk cleanup**, or prune `./data/audio` yourself.

## Troubleshooting

### App exits at startup: `ValueError: OPENAI_API_KEY is not set`
**Cause:** A required setting is missing — the app fails fast by design rather than mid-request.
**Solution:** Set `OPENAI_API_KEY` in `.env` (local) or inject it via `env_file`/`-e` (Docker).

### Status: "Invalid API key — check your .env"
**Cause:** The key is present but rejected by OpenAI (typo, revoked, or no TTS access).
**Solution:** Confirm the key is valid and TTS-enabled; regenerate it if needed.

### Status: "Rate limited — please retry shortly"
**Cause:** You hit your OpenAI rate or quota limit.
**Solution:** Wait and retry, space out batch items, or raise your plan limits.

### Status: "Connection error — please check your network"
**Cause:** The app couldn't reach the OpenAI API.
**Solution:** Check outbound network/DNS and any proxy or firewall between the host and OpenAI.

### Docker: container keeps restarting / the UI never responds
**Cause:** Usually a startup config error (e.g. missing `OPENAI_API_KEY`) or an unwritable data dir.
**Solution:** Read `docker compose logs`. Ensure `.env` has the key and `./data` is writable by
uid 999 (see next entry).

### Docker: `PermissionError` writing to `/app/data`
**Cause:** The bind-mounted `./data` isn't writable by the container's non-root user (uid 999).
**Solution:**
```bash
mkdir -p data && sudo chown -R 999:999 data
```

### Docker: UI unreachable from another machine
**Cause:** `HOST` was set to `127.0.0.1`/`localhost`, which is unreachable outside the container.
**Solution:** Keep `HOST=0.0.0.0` (the default) and reach the app via the host's address and mapped port.

### Port already in use
**Cause:** Another process holds the port (default `7860`).
**Solution:** Set a different `PORT` in `.env` (local), or `PORT=8080 docker compose up -d` (Docker).

### No inline player for a PCM file
**Not a bug.** PCM is raw audio with no container, so it's download-only with a note. Use
mp3/opus/flac/wav if you want inline preview.

### "Tags not supported" for PCM or AAC
**Not a bug.** PCM has no container, and OpenAI returns raw ADTS for AAC (not an M4A box mutagen can
tag). Generation still completes; tagging is skipped with a notice.

### WAV tags don't show up in my player
**Cause:** WAV carries ID3 tags, which some players ignore.
**Solution:** Use mp3, flac, or opus for broad tag compatibility.

### Library is empty after a redeploy
**Cause:** Data wasn't on the persistent mount, or the volume was deleted.
**Solution:** Confirm `./data` is bind-mounted and you never ran `docker compose down -v`. Audio
lives under `./data/audio`, history in `./data/echoquize.db`.

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

## Extending the app (Spec Kit workflow)

Echoquize is built with [Spec Kit](https://github.com/github/spec-kit) — spec-driven development
where each step produces artifacts that feed the next. To **add a new feature**, start a new
numbered spec (e.g. `specs/002-…`) and reuse the existing
[constitution](./.specify/memory/constitution.md). Each command below is run as a `/speckit.<name>`
slash command.

| Step | Command | What it does | Output |
|------|---------|--------------|--------|
| 1 | `/speckit.specify` | Describe the feature in natural language → creates a feature branch + spec | `specs/00N-…/spec.md` (user stories, FRs, success criteria) |
| 2 | `/speckit.clarify` | Asks up to 5 targeted questions and writes the answers back into the spec | updated `spec.md` |
| 3 | `/speckit.plan` | Generates the implementation plan and design artifacts; runs the Constitution Check | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| 4 | `/speckit.tasks` | Produces a dependency-ordered task list | `tasks.md` |
| 5 | `/speckit.analyze` | Cross-checks spec ↔ plan ↔ tasks for gaps and inconsistencies (non-destructive) | analysis report |
| 6 | `/speckit.implement` | Executes the tasks in order | code + manual validation |

The **minimum** path is `specify → plan → tasks → implement`; `clarify` and `analyze` are quality
gates worth keeping for anything non-trivial.

**Supporting commands**

- `/speckit.constitution` — create or amend the project principles (current: `v1.0.0`). A new
  feature's plan is checked against it.
- `/speckit.checklist` — generate a custom quality checklist for the feature.
- `/speckit.taskstoissues` — turn `tasks.md` into GitHub issues.
- `/speckit.agent-context-update` — refresh the managed Spec Kit section in `CLAUDE.md` (e.g. point
  "Active feature" at the new spec).

## License

No license file is present yet. Add a `LICENSE` to declare usage terms before sharing publicly.
