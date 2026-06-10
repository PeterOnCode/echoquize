# Feature Specification: TTS Studio Enhancements

**Feature Branch**: `002-studio-enhancements`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Nine related enhancements to the existing Echoquize TTS app: batch-queue file upload, per-row queue editing, title-derived filenames, YYYY/MM/DD storage, version display, bump-my-version tooling, expanded ID3v2.4.0 tag support with DB persistence, Library file-detail editing, and Generate-tab default tag values. Treat as one combined feature spec." (full details in `plan-tasks.txt`)

## Overview

This feature bundles nine independently valuable enhancements to the existing Echoquize
single-user text-to-speech studio. They cluster into three themes — **batch workflow** (bulk
upload, per-row editing), **metadata & files** (richer tags, readable filenames, dated storage,
Library editing), and **release/visibility** (version display, one-command version bumping).
They are specified together because several depend on a shared, expanded audio-tag set and on
shared file-naming/storage rules.

**Dependencies between stories** (carried from the source notes):

- Title-derived filenames (US4) and day-level storage (US6) together define the on-disk layout
  `…/YYYY/MM/DD/<title-slug>.<ext>`; the filename collision check is scoped to that day folder.
- Per-row queue editing (US3), Library editing (US5), and default tag values (US7) all reference
  the **expanded tag set defined in US2**; US2 is the authority for which tags exist.
- Library file-detail editing (US5) reuses US4's slug rules and US6's dated folder, and renames
  existing files in place on user request (distinct from US4's "no bulk migration" rule for
  generation-time naming).
- App version display (US8) and one-command version bumping (US9) share a single authoritative
  version value.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk-load the batch queue from a text file (Priority: P1)

A user has an existing document (a script, a list of phrases, lines of dialogue) and wants each
line turned into its own audio clip. Instead of typing each item into the batch queue by hand,
they upload a plain-text file and the queue fills automatically — one item per line.

**Why this priority**: This is the single biggest time-saver in the bundle and is fully
self-contained — it delivers value even if nothing else ships.

**Independent Test**: Upload a `.txt` file with several lines (including a blank line and one
over-length line) into the Batch queue and confirm one queue item is created per valid line, in
order, with an accurate added/skipped/rejected summary — without generating anything.

**Acceptance Scenarios**:

1. **Given** an empty batch queue, **When** the user uploads a UTF-8 `.txt` file with 5 non-empty
   lines, **Then** 5 queue items are created in the file's original order and a summary reports "5
   added".
2. **Given** a queue that already has 2 items, **When** the user uploads a file with 3 lines,
   **Then** the 3 new items are appended after the existing 2 (none replaced or cleared).
3. **Given** a file containing blank/whitespace-only lines, **When** it is uploaded, **Then** those
   lines create no items and the summary reports how many blank lines were skipped.
4. **Given** a file where one line exceeds 4096 characters, **When** it is uploaded, **Then** the
   valid lines are added, the over-length line is rejected with a message identifying it, and
   nothing is generated.
5. **Given** newly added items from an upload, **When** the user inspects them, **Then** each
   carries the voice/model/format/speed currently selected in the form and remains editable.

---

### User Story 2 - Richer, standards-based audio tags (Priority: P1)

A user wants to tag generated audio with more than the current six fields — including track
number, language, a full recording date, and arbitrary custom text/URL entries — and have MP3/WAV
files written to the modern ID3v2.4.0 standard. The expanded set is available everywhere tags are
edited and is remembered so it can be viewed and changed later.

**Why this priority**: It is the foundation the other tag-related stories (US3, US5, US7) build
on, and it directly increases the value of every saved generation.

**Independent Test**: On the Generate form, set the new fields (track, language, recording date,
a custom text entry, a custom URL), generate an MP3, and confirm the file carries ID3v2.4.0 tags
and that re-opening the item later shows the same values.

**Acceptance Scenarios**:

1. **Given** the Generate form, **When** the user fills Title, Artist, Album, Genre, Comment,
   Recording date, Track number, Language(s), and custom text/URL entries and generates an MP3,
   **Then** the file is written with ID3 v2.4.0 tags reflecting those values.
2. **Given** a recording-date field, **When** the user enters a year only ("2026") or a full date
   ("2026-06-10"), **Then** both are accepted.
3. **Given** a FLAC or Opus target, **When** the user sets the expanded fields, **Then** fields
   with a native equivalent are written and fields without one are skipped with a notice (no
   error).
4. **Given** an AAC or PCM target, **When** the user sets tags, **Then** tagging is skipped with a
   notice and the generation still completes.
5. **Given** a saved item with expanded tags, **When** the app is restarted and the item is viewed
   again, **Then** all tag values (including custom and multi-value entries) are still present.

---

### User Story 3 - Edit batch queue items in place (Priority: P2)

A user reviewing a queued batch wants to fix a typo, switch a voice, change a format, adjust voice
instructions, or set per-item tags on a specific row — without deleting and re-adding the item.

**Why this priority**: High everyday value for batch users; depends on the expanded tag set (US2)
for its tag fields.

**Independent Test**: Add several items to the queue, then edit one row's text, voice, model,
format, instructions, and tags, and confirm only that item changes and the edits are reflected
immediately.

**Acceptance Scenarios**:

1. **Given** a queued item, **When** the user edits its text, voice, model, or format on the row,
   **Then** only that item changes and the new values are shown immediately.
2. **Given** a queued item, **When** the user edits its text to be empty or over 4096 characters,
   **Then** the edit is rejected with a clear message and the previous valid text is kept.
3. **Given** a queued item using gpt-4o-mini-tts with voice instructions, **When** the user changes
   its model to tts-1, **Then** the instructions are kept on the row but are not sent at generation.
4. **Given** a queued item with tags, **When** the user changes its format to a non-taggable one
   (AAC/PCM), **Then** the user is told its tags will be skipped and the entered values are not
   discarded.
5. **Given** edits to one row, **When** the user clicks "Generate all", **Then** the output
   reflects the edited values for that item only.

---

### User Story 4 - Recognizable, title-based filenames (Priority: P2)

Today every file is named with a random identifier. A user wants saved files to be named from the
generation's title so they are recognizable on disk and in downloads, while remaining unique.

**Why this priority**: A visible quality improvement and the naming foundation reused by Library
editing (US5).

**Independent Test**: Generate two items with the same title and confirm the first is named from
its slugified title and the second gets a numeric suffix — neither overwrites the other.

**Acceptance Scenarios**:

1. **Given** a title "My Great Clip!", **When** a file is generated, **Then** its name stem is the
   slug "my_great_clip" (transliterated, lowercased, spaces→underscores, special characters
   removed, ≤64 chars), with the format's extension appended.
2. **Given** an existing file in the same dated folder with that name, **When** another file with
   the same title is generated, **Then** the new file gets a numeric suffix ("…_2") and the
   existing file is never overwritten.
3. **Given** an empty title, or a title that slugifies to nothing (e.g. non-Latin script),
   **When** a file is generated, **Then** the system falls back to a unique identifier so a valid
   filename always exists.
4. **Given** a generated file, **When** it is previewed, downloaded, deleted, or its tags edited,
   **Then** all actions resolve to the correct file via the stored path.

---

### User Story 5 - Edit file details from the Library (Priority: P2)

A user browsing the Library wants to correct a saved item's details — rename the file and edit its
full tag set — by selecting its row and saving, without re-generating.

**Why this priority**: Completes the metadata story; depends on the expanded tags (US2) and the
slug rules / dated folder (US4, US6).

**Independent Test**: Select a saved Library item, change its filename and several tags in the edit
form, save, and confirm the file is renamed on disk, the tags are updated, and preview/download
still work.

**Acceptance Scenarios**:

1. **Given** a saved item, **When** the user selects its row, **Then** an edit form/panel opens
   showing its current filename and full tag set.
2. **Given** the edit form, **When** the user types a new filename and saves, **Then** the name is
   normalized by the same slug rules, the file is renamed on disk, the stored path is updated, and
   the final saved name is shown.
3. **Given** a new filename that collides within the dated folder, **When** the user saves, **Then**
   a numeric suffix is appended and the final name reported.
4. **Given** a new filename that is empty or slugifies to nothing, **When** the user saves, **Then**
   it is rejected with a clear message and the existing filename is kept (no silent identifier
   substitution).
5. **Given** the user edits the title in this form, **When** they save, **Then** the file is NOT
   auto-renamed (the filename changes only via the explicit rename field).
6. **Given** an AAC/PCM item, **When** the user edits details, **Then** the filename is still
   editable while tag writing is skipped with a notice.

---

### User Story 6 - Day-level storage folders (Priority: P3)

Files accumulate over time. A user (or operator inspecting the host) wants generated audio
organized into year/month/day folders so each folder stays small and files are easy to locate by
date.

**Why this priority**: Small, mostly invisible improvement; pairs with US4 to define the layout.

**Independent Test**: Generate a file and confirm it is written under a `YYYY/MM/DD` folder matching
its UTC creation date, while previously stored files remain readable in place.

**Acceptance Scenarios**:

1. **Given** a new generation on 2026-06-10 (UTC), **When** the file is saved, **Then** it is stored
   under a `2026/06/10/` folder.
2. **Given** any configured storage destination, **When** files are saved, **Then** the same
   day-level layout is used.
3. **Given** files saved under the older month-level layout, **When** the user browses or plays
   them, **Then** they still resolve correctly (no migration required).

---

### User Story 7 - Default tag values on the Generate tab (Priority: P3)

A user who tags generations the same way every time (e.g. a fixed artist/album) wants the tag
fields pre-filled with their defaults so they don't retype them for each clip, while still being
able to override per generation.

**Why this priority**: A convenience layered on the expanded tag set (US2); low effort, no new
user-facing storage.

**Independent Test**: Configure default tag values, open the Generate tab, and confirm the tag
fields are pre-filled and can still be overridden or cleared.

**Acceptance Scenarios**:

1. **Given** configured default tag values, **When** the Generate tab loads or resets, **Then** the
   corresponding tag fields are pre-filled with those defaults and unset defaults remain blank.
2. **Given** pre-filled defaults, **When** the user changes or clears a field before generating,
   **Then** the user's value is used (defaults never force a value).
3. **Given** configured defaults, **When** the user adds a new batch-queue item, **Then** the new
   item's tags are seeded with the same defaults and remain editable.
4. **Given** the title field, **When** defaults are applied, **Then** the title is not defaulted.

---

### User Story 8 - App version shown in the header (Priority: P3)

Anyone using a deployed instance wants to see which version they are running at a glance, shown
near the app title.

**Why this priority**: Small, self-contained visibility improvement.

**Independent Test**: Open the app and confirm the current version appears near the title on load.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** a user loads any tab, **Then** the current version is
   shown near the title (e.g. "v0.1.0") as unobtrusive text.
2. **Given** the version cannot be determined, **When** the app starts, **Then** it starts normally
   and the version is omitted or shown as a neutral placeholder (no startup error).

---

### User Story 9 - One-command version bumping (Priority: P3)

A maintainer wants to release a new version by running one command that updates the single
authoritative version and records the release, rather than editing version strings by hand.

**Why this priority**: Developer/release tooling; pairs with US8 but does not affect end users
beyond the version reported.

**Independent Test**: Run the bump command for a patch release and confirm the authoritative
version is updated, a release commit and tag are created, and the UI reflects the new version with
no further edits.

**Acceptance Scenarios**:

1. **Given** the current version, **When** the maintainer runs the bump command for major, minor,
   or patch, **Then** the authoritative version updates consistently and the next/current version
   can be shown.
2. **Given** a bump, **When** it completes, **Then** a release commit and an annotated tag are
   created.
3. **Given** a completed bump, **When** the app is reloaded, **Then** the header shows the new
   version with no additional manual change.

---

### Edge Cases

- **All-blank upload**: a file with only blank/whitespace lines creates 0 items; the summary
  reports all lines skipped.
- **Mixed valid/over-length upload**: valid lines are queued, over-length lines are listed as
  rejected, and nothing is generated until "Generate all".
- **Duplicate titles in the same day folder**: the second file receives a numeric suffix; no file
  is overwritten.
- **Un-sluggable title**: a title that yields an empty slug (e.g. emoji-only or a non-Latin script
  with no ASCII transliteration) falls back to a unique identifier.
- **Over-long title**: a slug longer than 64 characters is truncated to 64 before any collision
  suffix is applied.
- **Format change after tagging (queue or Library)**: switching to a non-taggable format warns that
  tags will be skipped but retains entered values.
- **Library rename collision / empty name**: a colliding new name gets a suffix (final name
  reported); an empty or un-sluggable new name is rejected and the original kept.
- **Version metadata unavailable**: the header gracefully omits the version instead of failing.
- **Invalid default-tag configuration**: an unreadable/invalid default leaves that field blank and
  the app still starts.
- **Custom URL on FLAC/Opus**: an entry with no native equivalent is skipped with a notice rather
  than erroring.

## Requirements *(mandatory)*

### Functional Requirements

**Batch queue from a text file (US1)**

- **FR-001**: Users MUST be able to upload a plain-text (`.txt`, UTF-8) file in the Batch queue
  area to populate the queue.
- **FR-002**: The system MUST split uploaded content on newline characters, creating one queue item
  per line and preserving the file's original line order.
- **FR-003**: Uploaded items MUST be appended to the existing queue without clearing or replacing
  existing items.
- **FR-004**: The system MUST trim leading/trailing whitespace per line and skip blank or
  whitespace-only lines (no empty items created).
- **FR-005**: Each item created from a line MUST inherit the voice/model/format/speed currently
  selected in the form and remain individually editable afterward.
- **FR-006**: The system MUST enforce the existing 4096-character-per-item limit per line, rejecting
  over-length lines with a message identifying them while still adding the valid lines.
- **FR-007**: After an upload, the system MUST show a summary of items added, blank lines skipped,
  and lines rejected for length.
- **FR-008**: The system MUST accept files with no enforced cap on line count or file size while
  remaining responsive during load.
- **FR-009**: The uploaded file MUST NOT be persisted; only the resulting (per-session) queue items
  exist, and nothing is generated until the user starts generation.

**Per-row batch queue editing (US3)**

- **FR-010**: Users MUST be able to edit an existing queue item's text, voice, model, format, voice
  instructions, and audio tags directly on its row before generation.
- **FR-011**: Editing an item's text MUST re-validate the 4096-character limit; an empty or
  over-length edit MUST be rejected with a clear message and the previous valid value retained.
- **FR-012**: Voice instructions MUST be sent only when the item's model is `gpt-4o-mini-tts`;
  changing the model away from it MUST retain entered instructions without sending them.
- **FR-013**: Per-row tag editing MUST follow per-format tag support; changing an item's format to a
  non-taggable one MUST warn that tags will be skipped without discarding entered values.
- **FR-014**: Item speed MUST remain unchanged by this capability (speed is out of scope for per-row
  editing).
- **FR-015**: An edit MUST affect only that item and only the output of generation, and edited
  values MUST be reflected immediately in the row.

**Title-derived filenames (US4)**

- **FR-016**: The system MUST name each newly generated audio file from the generation's title by
  applying these slug rules to produce the filename stem: transliterate accented/Latin characters
  to ASCII, lowercase, convert spaces to underscores, remove characters outside `[a-z0-9_-]`,
  collapse/trim separators, and cap the stem at 64 characters (excluding the extension).
- **FR-017**: The system MUST guarantee filename uniqueness within the file's dated folder by
  appending a numeric suffix on collision (kept within the 64-character cap) and MUST never
  overwrite an existing file.
- **FR-018**: When the title is empty or yields an empty slug, the system MUST fall back to a unique
  identifier so a valid filename always exists.
- **FR-019**: The stored record MUST reference the actual saved filename/path so preview, download,
  delete, and tag-edit resolve to the real file.
- **FR-020**: Title-derived naming MUST apply to newly generated files only; existing files MUST NOT
  be renamed or migrated.

**Day-level storage (US6)**

- **FR-021**: The system MUST store newly generated audio under a `YYYY/MM/DD` folder derived from
  the generation's UTC creation date.
- **FR-022**: The dated-folder layout MUST apply uniformly across every storage backend.
- **FR-023**: Filename-uniqueness checks MUST be scoped to the day folder.
- **FR-024**: Files saved under the previous layout MUST remain in place and readable at their stored
  paths (no migration).

**Version display (US8)**

- **FR-025**: The system MUST display the application version near the app title, visible on load,
  sourced from a single authoritative version value read at runtime.
- **FR-026**: If the version cannot be determined, the system MUST degrade gracefully (omit or show a
  placeholder) rather than failing at startup.
- **FR-027**: Version display MUST be display-only — no remote version check, comparison, or update
  prompt.

**Version bumping (US9)**

- **FR-028**: Maintainers MUST be able to bump the project version's major, minor, or patch part
  with a single command that updates the single authoritative version consistently.
- **FR-029**: A version bump MUST create a release commit and an annotated version tag.
- **FR-030**: A bump MUST be reflected in the UI version display without any further manual edit.
- **FR-031**: The project MUST maintain a single authoritative version (no second hardcoded copy),
  and the bump MUST be exposed via the project's task runner.

**Expanded ID3v2.4.0 tags & persistence (US2)**

- **FR-032**: The audio tag set MUST be expanded to include Title, Artist, Album, Genre, Comment,
  Recording date/time, Track number, Language(s), Custom text field(s), and Custom URL field(s),
  available everywhere tags are edited (Generate form, batch items, Library editor).
- **FR-033**: MP3 and WAV tags MUST be written conforming to ID3 version 2.4.0.
- **FR-034**: The Recording date/time field MUST accept a full timestamp and also accept year-only
  input, replacing the prior year-only field.
- **FR-035**: For FLAC and Opus, supported fields MUST map to their native metadata equivalents;
  fields with no equivalent MUST be skipped with a notice. AAC and PCM remain untaggable and MUST be
  skipped gracefully.
- **FR-036**: Saving tags MUST replace the full tag set (clearing a field removes it, setting it
  writes it), and the generation MUST still complete when tagging is skipped.
- **FR-037**: Tag values MUST be persisted in the system's authoritative tag store so they display
  and can be re-edited later; existing records and their prior year/date values MUST keep working
  (backward compatible).
- **FR-038**: Custom text and custom URL entries MUST be description-keyed so multiple distinct
  entries can coexist on one item.

**Library file-detail editing (US5)**

- **FR-039**: Users MUST be able to select a saved Library item and edit its filename and full tag
  set via an edit form/panel, saving changes to both the file and the stored record.
- **FR-040**: Library filename editing MUST be a manual rename validated by the same slug rules
  (including the 64-character cap and collision suffix scoped to the dated folder), reporting the
  final saved name; an empty or un-sluggable new name MUST be rejected (no silent identifier
  substitution).
- **FR-041**: A rename MUST update the file on disk and the stored path so all flows resolve to the
  real file; editing the title MUST NOT auto-rename the file.
- **FR-042**: The file extension MUST NOT be editable.
- **FR-043**: This editor MUST become the single place to edit a saved item's tags, covering the
  full expanded set; for untaggable formats, tag writing is skipped while the filename remains
  editable.

**Default tag values (US7)**

- **FR-044**: The Generate tab's tag fields MUST be pre-filled from configured default tag values on
  form load/reset, leaving fields with no configured default blank.
- **FR-045**: Users MUST be able to override or clear any pre-filled default per generation;
  defaults MUST never force a value.
- **FR-046**: Configured defaults MUST also seed the tags of newly added batch-queue items, which
  remain individually editable.
- **FR-047**: The Title field MUST NOT be defaulted.
- **FR-048**: Missing or invalid default configuration MUST fall back to blank fields rather than
  failing at startup.

### Key Entities *(include if feature involves data)*

- **Generation Record**: One saved generation. Extended by this feature with the expanded tag values
  (track number, languages, custom text/URL entries) and a generalized recording date/time (the
  prior year value remains valid); its stored path reflects the title-derived filename within a
  `YYYY/MM/DD` folder. Remains the authoritative source for what the Library displays and edits.
- **Batch Queue Item**: An ephemeral, per-session queued request. Now fully editable (text, voice,
  model, format, voice instructions, tags) and creatable in bulk from an uploaded file. Not
  persisted.
- **Tag Set**: The expanded, ID3v2.4.0-aligned set of metadata fields, with per-format
  applicability (full support for MP3/WAV; native equivalents for FLAC/Opus; skipped for AAC/PCM).
- **Default Tag Configuration**: Deployment-provided default values for tag fields, applied to new
  generations and new queue items; not user-editable in the app.
- **Application Version**: The single authoritative version value, displayed in the UI and updated
  by the bump capability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can turn a multi-line text file into a fully populated batch queue in a single
  upload action, with no per-line manual entry.
- **SC-002**: After an upload, the reported added / skipped-blank / rejected-too-long counts exactly
  match the contents of the uploaded file.
- **SC-003**: A user can correct any queued item's text, voice, model, format, instructions, or tags
  before generating without removing and re-adding the item.
- **SC-004**: 100% of newly generated files have a human-readable name derived from their title, and
  no generation ever overwrites an existing file.
- **SC-005**: Newly generated files can be located by date within a year/month/day folder structure,
  and previously saved files remain playable.
- **SC-006**: Anyone viewing the app can identify the running version from the header at a glance.
- **SC-007**: A maintainer can release a new version (update + release commit + tag) with a single
  command, and the UI reflects the new version with no further edits.
- **SC-008**: A user can set and later edit the full expanded tag set (including track, language,
  custom text/URL, and full recording date) on any taggable format, and the values survive an app
  restart.
- **SC-009**: A user can rename a saved file and edit all its tags from the Library, and every
  subsequent preview, download, and delete resolves to the renamed file.
- **SC-010**: A user who has configured default tags sees them pre-filled on every new generation
  without retyping and can still override them.

## Assumptions

- **Combined delivery**: The nine enhancements are specified as one feature with the dependencies
  described in the Overview (US4+US6 define the on-disk layout; US2 owns the tag set referenced by
  US3/US5/US7; US5 reuses US4's slug rules and US6's dated folder; US8/US9 share one version value).
- **Default tag values are deployment configuration** (provided via the environment, consistent with
  the project's config-as-environment principle), not an in-app settings screen — no new user-facing
  persistence surface is introduced.
- **Single authoritative version**: the project's package version is the single source of truth,
  read at runtime; the UI reads that same value.
- **Version-bump tooling**: the one-command bump capability is provided by adopting the
  `bump-my-version` tool, configured in the project and added as a project dev dependency (pinned
  and reproducible, per the constitution).
- **New-files-only** for title-derived naming (US4) and dated-folder storage (US6): existing files
  are left untouched; there is no bulk rename or move. Library editing (US5) renames an individual
  file only on explicit user request.
- **Tag persistence model is unchanged in spirit**: the database remains the authoritative source
  for tag values (the app does not re-read tags from files); the new fields are persisted alongside
  the existing ones, and the schema change is additive and backward compatible.
- **ID3v2.4.0 scope**: applies to MP3/WAV output. FLAC/Opus use their native metadata equivalents;
  AAC and PCM remain untaggable and are handled gracefully (per the project's tag-format reality).
- **Per-session queue behavior is unchanged**: uploaded files and queue contents are not persisted;
  only completed generations are saved.
- **Transliteration** of titles covers Latin/accented characters to ASCII; scripts with no ASCII
  transliteration fall back to a unique identifier for the filename.
