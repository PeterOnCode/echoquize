# Quickstart & Validation Guide: Echoquize

**Date**: 2026-06-08 | **Feature**: 001-echoquize-tts

This is the **validation guide** — how to run Echoquize and prove each user story works end to end.
It is the manual acceptance suite (Constitution Principle VI — no automated tests in scope).
Implementation details live in `tasks.md`; interface details in `contracts/`; entities in
`data-model.md`.

## Prerequisites

- uv 0.9+ (`uv --version`)
- Docker Engine 24+ and Docker Compose v2 (for US4 validation)
- An OpenAI API key with TTS access
- Git (repo already initialized)

## Setup (local dev)

```bash
uv sync                       # installs locked deps into .venv
cp .env.example .env          # then edit: set OPENAI_API_KEY=sk-...
uv run app.py                 # serves the UI
```

Expected: UI reachable at `http://localhost:7860`. Missing `OPENAI_API_KEY` → app exits at startup
with a clear `ValueError` (see `contracts/config.md`), **not** a later runtime failure.

---

## US1 — Generate & download (P1, MVP)

1. Open `http://localhost:7860` → **Generate** tab.
2. Enter a sentence, leave defaults (voice `alloy`, model `tts-1`, format `mp3`, speed `1.0`).
3. Click **Generate**.

**Expected** (FR-001–006, SC-001):
- Audio preview plays inline; a downloadable `.mp3` is offered.
- Status shows success + file size.
- File written under `audio/YYYY/MM/<uuid>.mp3`; a row exists in `echoquize.db`.
- Change voice/format/speed and regenerate → output reflects the choices.
- Select `pcm` → no inline player, download offered, note shown (FR-004).

**REPL checks** (contracts):
```bash
uv run python -c "from src.tts.client import generate_speech; print(len(generate_speech('hello','tts-1','alloy','mp3',1.0)),'bytes')"
uv run python -c "from src.db.database import init_db, list_generations; init_db(); print(list_generations(limit=1))"
```

---

## US2 — Batch & persistent library (P2)

1. In **Generate → Batch**, add 3 texts with different voices; **Generate All**.
2. Confirm 3 files produced and a single **zip** download (FR-008).
3. Open **Library**: all past generations listed with metadata; **filter by voice** narrows the list;
   row-select previews audio.
4. **Delete Selected** → row and file removed. **Bulk cleanup** by date/voice → confirmation →
   matching rows + files removed (FR-010).
5. **Restart** `uv run app.py` → Library still shows prior generations (FR-011, SC-002).

**Scale check (SC-009):** with ~1,000 rows present, the Library loads a page (50) without noticeable
delay; paging/filter stay responsive.

---

## US3 — Audio tags (P3)

1. **Generate** tab → open **Audio Tags** accordion → set Title + Artist → generate an **mp3**.
2. Open the file in VLC → Info → Title/Artist present (FR-013, SC-005).
3. **Library** → select an mp3 → edit Comment → **Save Tags** → reopen file → change persisted.
4. Generate a **pcm** with tags filled → generation completes; status notes tags skipped (FR-014).
5. Select an **aac**/**pcm** item in Library → Save Tags disabled with a notice.

**REPL checks:**
```bash
uv run python -c "from src.tags.writer import write_tags; write_tags('x.pcm','pcm',{})"   # → TagsNotSupportedError
```

---

## US4 — Self-host & operate (P4)

```bash
mkdir -p data && sudo chown -R 999:999 data        # volume writable by the non-root uid 999
docker compose up -d --build
curl -I localhost:7860                              # → HTTP 200
```

**Expected** (FR-015–019, SC-006/008):
- UI reachable on the configured port; `docker run -e PORT=8080 -p 8080:8080 echoquize` serves on 8080.
- Missing `OPENAI_API_KEY` → container fails fast with a clear message.
- Optional auth: set `UI_USERNAME`/`UI_PASSWORD` in `.env` → login required; unset → open.
- Generate a file, then `docker compose down && docker compose up -d` → file still in Library, and
  visible on host under `./data/audio/` (SC-008). **Never** run `docker compose down -v` (destroys data).
- Image contains no `uv` binary and no `.env`/`audio/`/`data/` (Principle IV).

---

## US5 — Swappable storage (P5)

```bash
uv run python -c "from src.storage import get_storage; print(type(get_storage()).__name__)"   # LocalStorage
STORAGE_BACKEND=bogus uv run python -c "from src.storage import get_storage; get_storage()"     # → ValueError
STORAGE_BACKEND=s3    uv run python -c "from src.storage import get_storage; get_storage().save(b'x','y')"  # → NotImplementedError (clear message)
```

**Expected** (FR-020/021, SC-007): default `local` works end to end; unknown backend → `ValueError`;
unimplemented backend → clear `NotImplementedError`; generate/browse behavior unchanged by the choice.

---

## Acceptance roll-up

| Story | Primary criteria |
|-------|------------------|
| US1 | SC-001; FR-001–006 |
| US2 | SC-002, SC-003, SC-009; FR-007–011 |
| US3 | SC-005; FR-012–014 |
| US4 | SC-006, SC-008; FR-015–019 |
| US5 | SC-007; FR-020–021 |
| Cross-cutting | SC-004 (friendly errors), FR-022–024 |
