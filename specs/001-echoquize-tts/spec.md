# Feature Specification: Echoquize — Self-Hosted Text-to-Speech Studio

**Feature Branch**: `001-echoquize-tts`

**Created**: 2026-06-08

**Status**: Draft

**Input**: User description: Echoquize, a self-hosted web application that turns written text into
downloadable speech audio, keeps a persistent library of every generation, lets users tag the
audio, and can be deployed and operated by a single owner on their own infrastructure.

## Clarifications

### Session 2026-06-08

- Q: Intended access / exposure model? → A: Private use (localhost, LAN, VPN, or behind the
  operator's own reverse proxy); the single-owner password is OFF by default; TLS/HTTPS is the
  operator's responsibility, not the application's.
- Q: Retention / storage-growth policy? → A: Manual deletion plus in-app bulk cleanup tools (e.g.,
  delete by date range or by voice); no automatic pruning.
- Q: Target library scale? → A: Up to low-thousands of items; the Library paginates (loads in pages
  with filtering applied) rather than loading the entire history at once.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate and download speech from text (Priority: P1)

A user opens the application, types or pastes some text, chooses how it should sound (which voice,
quality level, audio format, and playback speed), and generates an audio version. They hear a
preview in the browser and download the file. The generation is automatically saved so it is never
lost.

**Why this priority**: This is the entire reason the product exists. With only this story, the user
already has a working tool that converts text to speech and gives them a file — a complete,
demonstrable MVP. Every other story builds on it.

**Independent Test**: Open the app, enter a sentence, pick a voice, click Generate, confirm the
audio plays inline and a file downloads. Fully delivers value on its own.

**Acceptance Scenarios**:

1. **Given** the app is open with default options, **When** the user enters text and generates,
   **Then** an audio preview plays in the browser and a downloadable file is produced.
2. **Given** a user changes voice, quality, format, and speed, **When** they generate, **Then** the
   resulting audio reflects the chosen options.
3. **Given** a generation succeeds, **When** the user looks at the status area, **Then** they see a
   confirmation including the file size, and the generation has been saved to the persistent record.
4. **Given** the chosen format cannot be played inline by the browser, **When** generation
   completes, **Then** the user is still offered the file to download with a clear note that inline
   preview is unavailable.

---

### User Story 2 - Batch generation and a persistent library (Priority: P2)

A user needs several audio clips at once. They add multiple texts — each with its own voice and
settings — to a queue, then generate them all in one action and download them together. Separately,
they can open a Library of every past generation, page through and filter it, replay any item, and
remove ones they no longer want — individually or in bulk (e.g., by date range or voice). The
library persists across restarts.

**Why this priority**: Turns a single-shot tool into a productive workspace. Batch saves repeated
effort; the library makes past work findable and reusable. Valuable, but only meaningful once
single generation (US1) exists.

**Independent Test**: Queue three texts with different voices, generate all, confirm three files
arrive in one bundle; then open the Library, confirm all past generations appear, filter by voice,
replay one, delete one and confirm it disappears.

**Acceptance Scenarios**:

1. **Given** several texts are queued with individual settings, **When** the user generates the
   batch, **Then** each item produces its own audio file and all are offered as a single download.
2. **Given** items are in the queue, **When** the user removes a selected item, **Then** it no
   longer generates.
3. **Given** past generations exist, **When** the user opens the Library, **Then** every prior
   generation is listed with its key details (when it was made, voice, quality, format, speed, a
   text preview, and file size).
4. **Given** the Library is open, **When** the user filters by a voice, **Then** only matching
   generations are shown.
5. **Given** a Library item is selected, **When** the user chooses to delete it, **Then** both the
   stored record and the underlying audio file are removed.
6. **Given** many generations exist, **When** the user runs a bulk cleanup (e.g., by date range or by
   voice), **Then** all matching items — records and their audio files — are removed in one action
   after confirmation.
7. **Given** the history is large (up to low-thousands of items), **When** the user opens the
   Library, **Then** results load in pages with filtering applied rather than all at once, and the
   list stays responsive.
8. **Given** generations were made earlier, **When** the application is restarted, **Then** those
   generations still appear in the Library.

---

### User Story 3 - Edit audio metadata tags (Priority: P3)

A user wants their audio files to carry proper metadata (title, artist, album, comment, genre,
year) so they show up correctly in media players and music apps. They can fill tags in before
generating, or edit the tags of any existing item in the Library later. Formats that cannot carry
tags are handled gracefully with a clear notice.

**Why this priority**: A quality-of-life enhancement that makes output files more useful, but the
product is fully functional without it.

**Independent Test**: Generate a taggable file with a title and artist, open it in a standard media
player, and confirm the tags appear; then edit a tag in the Library, reopen the file, and confirm
the change persisted.

**Acceptance Scenarios**:

1. **Given** a user fills in title and artist before generating a taggable format, **When** they
   generate, **Then** those tags are present when the file is opened in a media player.
2. **Given** a saved generation in a taggable format, **When** the user edits its tags in the
   Library and saves, **Then** the change is written to the file and persists across restarts.
3. **Given** the chosen format cannot carry tags, **When** the user supplies tags anyway, **Then**
   generation still succeeds and the user sees a clear "tags not supported for this format" notice
   instead of an error or a silent failure.
4. **Given** a non-taggable item is selected in the Library, **When** the user views the tag editor,
   **Then** saving tags is disabled with an explanation.

---

### User Story 4 - Self-host and operate the application (Priority: P4)

An operator (who may be the same person as the user) deploys the application onto their own
infrastructure, configures it with their credentials and preferences, optionally protects it with a
password, and runs it as a long-lived service. Their audio and history survive upgrades and
restarts.

**Why this priority**: Required to actually run the tool beyond a developer's laptop, but the
application's user-facing value (US1–US3) is defined independently of where it runs.

**Independent Test**: Following the documented steps, deploy the app on a clean host, reach the
working UI, generate a file, then perform a full restart/rebuild cycle and confirm the file is still
present in the Library.

**Acceptance Scenarios**:

1. **Given** the documented deployment steps, **When** an operator deploys on a fresh host, **Then**
   the working UI is reachable at the configured address and port.
2. **Given** the operator sets credentials/preferences through configuration, **When** the app
   starts, **Then** it uses those values without any change to the application itself.
3. **Given** a required credential is missing, **When** the app starts, **Then** it fails
   immediately with a clear message rather than failing later during use.
4. **Given** the operator enables the optional password, **When** a visitor opens the app, **Then**
   they must authenticate; with the password unset, no login is required.
5. **Given** generated audio and history exist, **When** the operator tears down and restarts the
   deployment (without an explicit purge), **Then** no audio or history is lost.

---

### User Story 5 - Swappable storage location (Priority: P5)

The owner wants the freedom to change where audio is stored — local disk now, a cloud object store
or shared drive later — without disrupting how people generate or browse audio. The default works
out of the box; alternative destinations are ready to be enabled later.

**Why this priority**: Future-proofing. It protects against storage growth and migration pain, but
delivers no new end-user capability today, so it is last.

**Independent Test**: Confirm the default storage works end-to-end; confirm that selecting an
unimplemented destination produces a clear, explanatory message and that no user-facing generation
or browsing behavior depends on the storage choice.

**Acceptance Scenarios**:

1. **Given** the default storage destination, **When** users generate and browse audio, **Then**
   everything works as in US1–US2.
2. **Given** the storage destination is changed through configuration, **When** users generate and
   browse audio, **Then** the experience is unchanged from their perspective.
3. **Given** an alternative destination that is not yet available is selected, **When** the owner
   attempts to use it, **Then** they receive a clear message explaining it is not yet enabled,
   rather than an unexplained failure.

---

### Edge Cases

- **Empty input**: Generation is refused with a "text is required" message before any external
  service is contacted.
- **Over-length input**: Text beyond the per-item limit is rejected with a clear message; in a
  batch, the limit applies to each item individually, not the total.
- **External service failure**: Invalid credentials, rate limiting, or service errors surface as
  friendly, actionable messages — never raw technical traces.
- **Non-previewable format**: Formats with no inline player skip the preview and offer download only,
  with a note.
- **Non-taggable format**: Tagging is skipped with a clear notice; generation still completes.
- **Limited-compatibility tags**: For formats whose tags some players ignore, the user is warned of
  the limitation.
- **Concurrent generations**: Multiple simultaneous requests (e.g., several browser tabs) must not
  corrupt the stored history.
- **Stale deletion**: Deleting an item whose underlying file was already removed externally still
  cleanly removes the record without crashing.
- **Interrupted batch**: If the session ends mid-batch, the ephemeral queue may be lost; already
  saved generations remain in the durable Library.
- **Storage growth over time**: The stored audio can grow large; users reclaim space through manual
  deletion and in-app bulk cleanup (by date range or voice). Automatic pruning is out of scope.

## Requirements *(mandatory)*

### Functional Requirements

**Generation (US1)**

- **FR-001**: Users MUST be able to enter free text up to a documented per-item character limit and
  generate spoken audio from it.
- **FR-002**: Users MUST be able to choose a voice, a quality level, an output audio format, and a
  playback speed before generating.
- **FR-003**: The system MUST offer a style/instruction option that applies only to the quality
  level that supports it, and MUST ignore it for the others without error.
- **FR-004**: On successful generation, the system MUST provide an inline preview when the format
  supports it and a downloadable file in all cases.
- **FR-005**: The system MUST display a clear status after each attempt — success details (including
  file size) or a friendly error.
- **FR-006**: Every successful generation MUST be saved to a durable record capturing its text,
  chosen options, file location, size, and creation time.

**Batch & Library (US2)**

- **FR-007**: Users MUST be able to add multiple generation requests, each with independent
  settings, to a queue and remove queued items before running.
- **FR-008**: Users MUST be able to generate all queued items in one action and receive the results
  together as a single download.
- **FR-009**: Users MUST be able to browse a **paginated** Library of past generations showing, at
  minimum: creation time, voice, quality, format, speed, a text preview, and file size, remaining
  responsive for histories up to low-thousands of items.
- **FR-010**: Users MUST be able to refresh the Library, filter it (e.g., by voice), replay a
  selected item, delete a selected item, and **bulk-delete** multiple items by filter such as date
  range or voice — in all deletion cases removing both the records and their audio files.
- **FR-011**: The Library MUST remain complete and accurate across application restarts and
  redeployments.

**Tags (US3)**

- **FR-012**: Users MUST be able to set metadata tags (title, artist, album, comment, genre, year)
  either before generating or by editing an existing Library item.
- **FR-013**: Saved tags MUST be written into the audio file for supported formats and MUST persist
  across restarts.
- **FR-014**: For formats that cannot carry tags, the system MUST skip tagging, inform the user, and
  still complete the generation.

**Operations & Configuration (US4)**

- **FR-015**: All runtime settings (credentials, storage location, history location, network
  address/port, optional access password) MUST be configurable by the operator without modifying
  the application.
- **FR-016**: The system MUST validate that required configuration is present at startup and fail
  immediately with a clear message when it is missing.
- **FR-017**: The system MUST support an optional single owner password that is OFF by default; when
  unset, access is open; when set, valid credentials are required. The application is intended for
  private deployment, with transport encryption (TLS/HTTPS) provided by the operator's environment
  rather than by the application itself.
- **FR-018**: Audio and history MUST persist across teardown, restart, and redeployment, and MUST
  NOT be destroyed except by an explicit, deliberate purge.
- **FR-019**: Distributable build artifacts MUST NOT contain secrets or user data; credentials MUST
  be supplied at run time.

**Storage Abstraction (US5)**

- **FR-020**: The storage destination MUST be selectable by configuration, defaulting to a working
  local destination, with the user-facing generation and browsing experience unchanged regardless of
  the destination chosen.
- **FR-021**: Selecting a not-yet-available destination MUST produce a clear explanatory message
  rather than an unexplained failure.

**Cross-cutting**

- **FR-022**: Input MUST be validated (non-empty, within length limit) before any external service
  call is made.
- **FR-023**: All failures from external services or invalid input MUST be presented as
  human-readable messages, never as raw technical traces.
- **FR-024**: Concurrent generations MUST NOT corrupt the durable history.

### Key Entities

- **Generation Record**: The durable history entry for one produced audio file — its source text,
  the chosen voice/quality/format/speed, where the audio lives, its size, when it was created, and
  its metadata tags. This record is the source of truth for what the Library displays.
- **Audio File**: The produced artifact a user previews, downloads, and (where supported) carries
  embedded metadata tags. The file is authoritative for external playback.
- **Batch Queue Item**: A pending, session-scoped generation request with its own settings; ephemeral
  and not part of the durable history until generated.
- **Tag Set**: The metadata (title, artist, album, comment, genre, year) attachable to an audio file
  and stored alongside its record.
- **Storage Destination**: The configurable place audio is kept; abstract enough that the location
  can change without affecting how users generate or browse.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can produce and download an audio file from a short text in under 30
  seconds of interaction, without consulting documentation.
- **SC-002**: 100% of successfully generated items remain listed and replayable in the Library after
  an application restart or redeployment.
- **SC-003**: A user can queue and generate at least 10 separate texts in a single batch and receive
  all results in one download.
- **SC-004**: Across every defined error condition (empty input, over-length text, invalid
  credentials, rate limiting, unsupported tagging), 100% of outcomes are human-readable messages and
  zero expose raw technical traces.
- **SC-005**: For every tag-supporting format, metadata set by the user appears correctly when the
  file is opened in a standard media player.
- **SC-006**: An operator can take a fresh host to a working, reachable UI in under 15 minutes by
  following the documented steps.
- **SC-007**: Changing the storage destination requires only a configuration change, with no change
  to how users generate or browse audio.
- **SC-008**: A full teardown-and-restart cycle (without explicit purge) results in zero loss of
  audio files or history.
- **SC-009**: The Library remains responsive — a page of results loads without noticeable delay —
  with a stored history of at least 1,000 generations.

## Assumptions

- **Single owner / personal scale**: The application targets one owner/operator and light, mostly
  single-user usage. Multi-tenant accounts, roles, and high-concurrency scaling are out of scope.
- **External speech service**: A third-party cloud text-to-speech service provides the actual voice
  synthesis; the operator supplies valid credentials for it. Voice, quality-level, format, and speed
  choices reflect what that service offers.
- **Per-item text limit**: The character limit applies to each individual generation (and to each
  batch item separately), consistent with the external service's per-request limit.
- **Ephemeral queue, durable library**: The batch queue lives only within a working session; the
  Library is the durable, persistent record of results.
- **Record vs. file authority**: The stored record is the source of truth for what the UI shows; the
  audio file is authoritative for external playback. The product does not attempt to reconcile tags
  edited outside the application.
- **Format trade-offs are acceptable**: Some formats cannot carry tags or cannot preview inline; the
  product surfaces these limitations rather than hiding or working around them.
- **Private deployment & transport security**: The application is intended for private access
  (localhost, LAN, VPN, or behind the operator's own reverse proxy). The owner password is off by
  default, and TLS/HTTPS is supplied by the operator's environment, not the application.
- **Retention**: Generations are kept indefinitely; space is reclaimed only by manual and bulk
  deletion within the app. No automatic age-, size-, or count-based pruning is in scope.
- **Library scale**: The Library is designed for up to low-thousands of generations, browsed via
  pagination and filtering. Tens-of-thousands-plus histories with dedicated search/indexing are out
  of scope.
- **Validation approach**: Per the project's pragmatic, single-user scope, acceptance is validated
  through hands-on functional checks per increment rather than a mandated automated test suite.
