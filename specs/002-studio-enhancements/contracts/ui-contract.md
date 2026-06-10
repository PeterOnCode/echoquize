# Contract: UI (`app.py`, `src/ui/*`, delta)

Behavioral deltas to the Gradio UI. Mechanics (Blocks, events, `gr.State`) follow the feature-001
ui-contract; only the new behavior is specified here.

## `app.py` — version in the header (US8)

- The title line shows the app version next to the title when available, e.g.
  `🔊 Echoquize — Text-to-Speech Studio  v0.1.0`, with the version as unobtrusive/muted text.
- Source: `src/version.py:app_version()`. When it returns `None`, the version is omitted; the app
  starts and renders normally regardless (FR-025–FR-027).

## `src/ui/generate_tab.py`

### Expanded + default tags (US2, US7)

- The "Audio tags" accordion exposes the full expanded set: Title, Artist, Album, Genre, Comment,
  Recording date (was "Year"), Track number, Language(s), and repeatable Custom text / Custom URL
  (each a description + value/URL).
- Non-title fields initialize from `config.DEFAULT_TAGS`; unset defaults render blank. Users may
  override or clear any field (FR-044, FR-045, FR-047).
- The format `info` text still notes which formats carry tags; AAC/PCM show the skip notice on
  generate (unchanged).

### Slug filenames (US4)

- `_on_generate` and `_generate_all` compute the stem via `naming.slugify(title)`, falling back to
  `uuid4().hex` when empty, and call `storage.save(audio, f"{stem}.{fmt}")`. The DB stores the
  returned path. The status line reports the actual saved filename (already does).

### File upload → queue (US1)

- A `gr.File(file_types=[".txt"])` in the Batch queue accordion. On upload: decode UTF-8,
  `splitlines()`, strip, skip blanks; validate each line ≤ `MAX_CHARS`; append a queue item per
  valid line (inheriting the current voice/model/format/speed and seeded tags from `DEFAULT_TAGS`),
  preserving file order; never clear the existing queue.
- Returns a summary: `"Added N — skipped B blank — rejected R too long (lines …)"` (FR-007).

### Per-row queue editing (US3)

- An "Edit selected item" panel (below the queue dataframe). On row select (existing
  `queue_df.select → selected_index`), load that item's text/voice/model/format/instructions/tags
  into editable widgets.
- "Update item" validates text (≤ `MAX_CHARS`, non-empty; else reject and keep prior value), writes
  the edited values back into `queue_state[index]`, and refreshes the queue view. Voice-instructions
  visibility follows model = `gpt-4o-mini-tts`; instructions are retained (not cleared) when the
  model changes (FR-012). Changing format to AAC/PCM shows a "tags will be skipped" notice without
  discarding entered tag values (FR-013).
- Speed is **not** editable here (FR-014).

## `src/ui/library_tab.py` — "Edit details" panel (US5)

- The "Edit tags" accordion becomes "Edit details", now the single editor for a saved item:
  - a **Filename** field showing the current stem (extension shown read-only/non-editable), plus
  - the full expanded tag set (same fields as the Generate accordion).
- On row select, fields populate from the record (`tag_*` columns + parsed `tags_extra`), and the
  filename stem from `basename(file_path)` minus extension.
- **Save**:
  1. If the stem changed: `stem = slugify(input)`; if empty → reject with a message, keep original
     (no UUID substitution, FR-040). Else `new_path = storage.rename(old_path, f"{stem}.{ext}")`
     (collision-safe; final name reported), then `update_file_path(gid, new_path)`.
  2. Write the expanded tags to the file (`write_tags`) and `update_tags(gid, …)`. For AAC/PCM, tag
     writing is skipped with a notice but the **filename is still editable** (FR-043).
  3. Reload the page so the table/state reflect the new name and tags.
- Editing the **title** never triggers a rename (FR-041); renaming is driven only by the Filename
  field.

**Guarantees** (all stories): every new failure path produces a friendly status message, never a
traceback (Principle VII); nothing is generated until the user clicks Generate / Generate all; the
batch queue and uploaded files remain per-session (not persisted).
