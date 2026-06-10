# Changelog

All notable changes to Echoquize are documented here.

## 0.1.0 — 2026-06-10

🎉 **First release.** Echoquize is a self-hosted text-to-speech studio: turn text into
downloadable speech with the OpenAI TTS API and keep every generation in a persistent,
browsable library — all running on your own infrastructure.

### ✨ New Features

- **Generate & download speech** — Type or paste text, pick a voice, model, format, and
  speed, then generate. You get an inline preview, a downloadable file, and a status line
  with the file size. Every generation is saved automatically.
- **Batch queue** — Line up several texts, each with its own voice and settings, and
  generate them all in one click. Every clip arrives together in a single zip.
- **Persistent library** — Browse every past generation, newest first, with full details
  (voice, model, format, speed, text preview, size). Filter by voice, page through results
  (50 per page), replay any item, delete one, or bulk-clean by date range and voice. Your
  history survives restarts and redeploys.
- **Audio tags** — Set title, artist, album, comment, genre, and year before generating, or
  edit them on any saved item later. Tags are written into the file and persist. Formats
  that can't carry tags are skipped gracefully with a clear notice instead of an error.
- **Self-hosting with Docker** — Ships as a multi-stage Docker image with Compose. Audio
  and history live on a host-visible `./data` mount, the container runs as a non-root user,
  and no secrets or data are baked into the image.
- **Swappable storage** — Stores audio on local disk by default, with S3 and Google Drive
  backends selectable purely by configuration — no code changes needed to switch.
- **Optional single-owner login** — Protect your instance with a username and password when
  you want it; leave it open for private localhost or LAN use.

### 🔧 Improvements

- **Clear, specific error messages** — Invalid API keys, rate limits, and network problems
  each surface a plain-language explanation instead of a raw stack trace.
- **Fail-fast startup** — A missing `OPENAI_API_KEY` stops the app at startup with an
  obvious message, so you never hit a confusing error mid-request.
- **Input validation up front** — Text is checked against the 4096-character limit *before*
  any API call; empty or over-length input is rejected immediately with a clear message.
- **`just` task runner** — Common workflows (install, run, verify, Docker up/down/logs) are
  available as one-line `just` recipes, including a recipe to pull secrets from Doppler.
- **Safer auth configuration** — Setting only one of the username/password pair now logs a
  startup warning and keeps access open, rather than failing silently.

### 🐛 Fixes

- Library records are now written only after the audio file is saved, so there are no
  orphan entries pointing at missing files.
- Creation timestamps are stored consistently in UTC, so date-range filtering and cleanup
  behave predictably.
- Deleting a library item whose file was already removed elsewhere now cleans up the record
  without erroring.
- Batch downloads are built reliably from in-memory audio.
- The batch queue selection clears correctly after you remove an item.
