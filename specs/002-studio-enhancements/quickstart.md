# Quickstart & Validation: TTS Studio Enhancements

**Feature**: 002-studio-enhancements | **Date**: 2026-06-10

Manual validation per the constitution (Principle VI — no automated suite). Each user story has an
**observable** success check (what actually happens), not a "file contains X" check. Run the app
with `uv run app.py` (or `just run`) and an `OPENAI_API_KEY` set, unless a step says "offline".

> Migration note: on first run against an existing `echoquize.db`, `init_db()` adds the
> `tag_track` and `tags_extra` columns. Confirm the app starts and the existing Library still lists
> prior generations (Principle V — no data loss).

## Prerequisites

- `uv sync` (after `bump-my-version` is added, this also installs it as a dev tool).
- A valid `OPENAI_API_KEY` for the generation stories; offline checks are marked.

---

## US1 — Bulk-load the batch queue from a text file (P1)

1. Create `sample.txt` with: a few normal lines, one blank line, one line > 4096 chars.
2. Generate tab → Batch queue → upload `sample.txt`.

**Expect**: one queue item per non-blank, in-length line, in file order; the over-length line and
blank line are **not** queued; a summary reads e.g. "Added 3 — skipped 1 blank — rejected 1 too
long (line 5)". Upload again → items **append** (queue grows, nothing replaced).

**Offline check**: `uv run python -c "from src.ui.generate_tab import _parse_upload"` style REPL on
the parse helper (split/strip/skip/validate) returns the expected added/skipped/rejected counts.

---

## US2 — Expanded ID3v2.4.0 tags (P1)

1. Generate an **MP3** with Title, Artist, Recording date `2026-06-10`, Track `1/10`, Language
   `eng`, a Custom text (`MOOD`/`calm`), and a Custom URL (`source`/`https://…`).
2. Inspect the file's tags (any tag viewer, or `mutagen` REPL).

**Expect**: the file carries **ID3v2.4.0** frames `TIT2/TPE1/TDRC/TRCK/TLAN/TXXX/WXXX` with those
values. Restart the app, open the item in the Library → all values (including custom/multi-value)
re-appear (persisted in DB). Repeat with **FLAC**: Vorbis fields present; the **custom URL** is
skipped with a notice (no error). **AAC/PCM**: generation completes with a "tags skipped" notice.

**Offline check**: REPL `write_tags(tmp.mp3, "mp3", {...})` then re-read with mutagen shows
`ID3` version `(2,4,0)` and the expected frames.

---

## US3 — Edit batch queue items in place (P2)

1. Add 2–3 items. Select a row → "Edit selected item".
2. Change its text, voice, model (to `gpt-4o-mini-tts`, set instructions, then back to `tts-1`),
   format (to `pcm`), and a tag; click "Update item".

**Expect**: only that row changes and the new values show immediately. Empty/over-length text is
rejected with a message and the prior text kept. Switching model away from `gpt-4o-mini-tts` keeps
the instructions text (not sent at generation). Switching to `pcm` shows a "tags will be skipped"
notice but keeps the entered tag values. Speed is not editable in this panel.

---

## US4 — Title-based filenames (P2)

1. Generate with Title "My Great Clip!" → note the saved filename in the status line.
2. Generate again, same title, same day.

**Expect**: first file saved as `my_great_clip.<ext>`; second as `my_great_clip_2.<ext>`; the first
file is **not** overwritten (both playable in the Library). Generate with an empty title → filename
falls back to a UUID stem. Generate with a non-Latin-only title (e.g. `日本語`) → UUID fallback.

**Offline check**: `slugify("Café déjà vu") == "cafe_deja_vu"`; `slugify("日本語") == ""`;
`len(slugify(<long>)) <= 64`.

---

## US5 — Edit file details from the Library (P2)

1. Select a saved item → "Edit details". Change the **filename** stem and several tags → Save.

**Expect**: the file is renamed on disk under its dated folder, the table shows the new name, and
preview/download/delete still work (path updated). A colliding new name gets a `_2` suffix and the
final name is reported. An empty/un-sluggable new name is rejected and the original kept. Editing
the **title** alone does **not** rename the file. For AAC/PCM, the filename is editable while tag
writing is skipped with a notice.

---

## US6 — Day-level storage folders (P3)

1. Generate a file.

**Expect**: it is written under `AUDIO_DIR/YYYY/MM/DD/` matching today's UTC date (inspect
`./data/audio/<YYYY>/<MM>/<DD>/` in Docker, or `./audio/...` locally). Previously saved files (older
`YYYY/MM/` layout) still play from the Library (read at their stored path).

---

## US7 — Default tag values on the Generate tab (P3)

1. Set `DEFAULT_TAG_ARTIST=Me` and `DEFAULT_TAG_ALBUM=Demos` in `.env`; restart.

**Expect**: the Generate tab's Artist/Album fields are pre-filled with those values on load; Title
is blank. Overriding/clearing a field uses the user's value. A newly added queue item carries the
same seeded tags. Unset defaults are blank. Set an env var to an odd value and confirm the app still
starts (no crash) — worst case the field is blank.

---

## US8 — App version in the header (P3)

1. Load any tab.

**Expect**: the version (e.g. `v0.1.0`) appears next to the title.

**Offline check**: `from src.version import app_version; app_version()` returns `"0.1.0"`. Temporarily
break `pyproject.toml`'s version read path → `app_version()` returns `None` and the app still
launches with the version omitted.

---

## US9 — One-command version bumping (P3, offline)

1. `just bump-patch` (wraps `uv run bump-my-version bump patch`).

**Expect**: `[project].version` and `[tool.bumpversion].current_version` both move `0.1.0 → 0.1.1`;
a release commit and an annotated tag (e.g. `v0.1.1`) are created. Reload the app → the header shows
`v0.1.1` with no other change. `uv run bump-my-version show` reports the current version.

> Run this in a clean working tree (the bump auto-commits). Revert the tag/commit if you are only
> testing.

---

## Regression / cross-cutting

- **Principle I**: `grep -rn "YYYY\|%Y/%m\|os.path.join.*audio" src/ui src/db` finds **no**
  path-layout construction outside `src/storage/` (and no directory listing for collisions).
- **Principle V**: start against a copy of an existing `echoquize.db`; the Library lists all prior
  items and they remain playable after the migration.
- **`just verify`**: extend the offline smoke checks to cover `slugify`, `app_version`, and the
  upload parser.
