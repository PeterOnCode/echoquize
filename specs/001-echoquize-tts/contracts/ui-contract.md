# Contract: src/ui/ + app.py (UI surface & behavior)

The Gradio Blocks app: two tabs over the service modules. This contract pins the user-facing surface
and event behavior that the spec's acceptance scenarios assert.

## app.py

- Builds `gr.Blocks()` with a **Generate** tab and a **Library** tab.
- `demo.launch(server_name=config.HOST, server_port=config.PORT, share=False)`.
- If `UI_USERNAME` and `UI_PASSWORD` are both set → `auth=(UI_USERNAME, UI_PASSWORD)`; else no auth
  (off by default — clarification Q1 / FR-017).
- Calls `init_db()` on startup.

## Generate tab (`generate_tab.py`)

**Single generation (US1):** Textbox (≤4096, char counter), Voice/Model/Format dropdowns, Speed
slider (0.25–4.0, step 0.05), Voice-Instructions textbox (visible only when model =
`gpt-4o-mini-tts`), Generate button, `gr.Audio` preview (filepath), `gr.File` download, Status box.

- On Generate: validate → `generate_speech()` → `get_storage().save()` → `write_tags()` if any tag
  set and format taggable → `insert_generation()` → return preview + file + status (size).
- `pcm`: skip inline preview (download-only) with a note (FR-004).
- Errors surface as friendly status, never tracebacks (FR-023).

**Tags accordion (US3):** collapsible, closed by default; six tag textboxes; PCM/AAC → notice that
tags are skipped.

**Batch (US2):** `gr.Dataframe` queue, Add-to-Queue, Remove-Selected, Generate-All (with
`gr.Progress`), `gr.File` zip download. Queue held in `gr.State` (ephemeral). Per-item 4096 limit.

## Library tab (`library_tab.py`)

- `gr.Dataframe`: ID, Created, Voice, Model, Format, Speed, Text preview (60 chars), File Size.
- Loaded via `list_generations(limit, offset, voice)` — **paginated** (page size 50) with page
  controls and a **Voice filter** dropdown (FR-009/010, SC-009).
- Refresh button; row-select → `gr.Audio` preview.
- **Delete Selected** → `delete_generation()` + `StorageBackend.delete()`.
- **Bulk cleanup** (by date range and/or voice) → confirmation → `bulk_delete()` + file removal
  (FR-010, readiness CHK013).
- **Edit Tags** panel: six fields pre-filled from the row; Save Tags → `write_tags()` + `update_tags()`;
  Clear Tags → empty tags written + DB cleared; PCM/AAC → Save disabled with notice.

## Guarantees

- Library reflects new generations after each generate and persists across restarts (FR-011/SC-002).
- No user action produces a raw traceback; all failures become readable status text (Principle VII).
