<!--
SYNC IMPACT REPORT
==================
Version change: (template) → 1.0.0
Bump rationale: Initial ratification of the Echoquize constitution (MAJOR — first adoption).

Principles defined (all new):
  I.   Storage Abstraction & Backend Independence
  II.  Reproducible, Pinned Builds
  III. Config-as-Environment (12-Factor)
  IV.  Secrets & Data Never in the Image
  V.   Durable Persistence
  VI.  Pragmatic Single-User Scope
  VII. Graceful, User-Facing Error Handling

Added sections:
  - Core Principles (7 principles)
  - Technology & Deployment Constraints
  - Development Workflow & Quality Gates
  - Governance

Removed sections: none (initial version)

Templates / dependent artifacts reviewed:
  - .specify/templates/plan-template.md ......... ✅ compatible (Constitution Check is a
        generic gate that resolves against this file; no hardcoded principle drift)
  - .specify/templates/spec-template.md ......... ✅ compatible (no mandatory sections
        contradicted; tech-agnostic success criteria unaffected)
  - .specify/templates/tasks-template.md ........ ✅ compatible (OPTIONAL tests align with
        Principle VI — no automated test suite mandated)
  - .claude/skills/speckit-*/ command guidance .. ✅ compatible (generic, no agent-name drift)
  - README.md / docs/quickstart.md .............. ⚠ none present at repo root (nothing to sync)

Deferred TODOs: none — RATIFICATION_DATE set to first adoption date (2026-06-08).
-->

# Echoquize Constitution

Echoquize is a self-hosted web application that converts text to speech via the OpenAI TTS
API, stores every generation in a persistent library (SQLite + local filesystem), and ships as
a Docker image run via Docker Compose. This constitution encodes the non-negotiable rules that
keep it portable, reproducible, secure, and pragmatically simple for personal single-user use.

## Core Principles

### I. Storage Abstraction & Backend Independence

All persistence of generated audio MUST flow through the `StorageBackend` ABC
(`src/storage/base.py`) and the config-driven `get_storage()` factory. No module outside
`src/storage/` may import storage-implementation classes directly or assume the local
filesystem layout. Swapping the backend (`local` → `s3` → `gdrive`) MUST require **zero**
changes to TTS, UI, or DB code — only a change to the `STORAGE_BACKEND` environment value.

**Rationale**: The plan commits to filesystem-now, S3/GDrive-later. The only way that promise
survives contact with real code is to forbid leakage of storage details into callers from day
one; a leaky abstraction is discovered too late to fix cheaply.

### II. Reproducible, Pinned Builds

Dependencies MUST be declared in `pyproject.toml` and pinned in `uv.lock`, and `uv.lock` MUST
be committed. Production and container installs MUST use `uv sync --frozen` (or
`--locked`) — never an implicit fresh resolution. Upgrading to newer compatible releases is
allowed only through a deliberate `uv lock --upgrade`. The Docker base-image Python (builder
and runtime stages) MUST match `.python-version` in lockstep; bumping the interpreter requires
bumping every stage together.

**Rationale**: "Newest, but reproducible" only holds if the lockfile is authoritative. An
implicit re-resolve on the VPS, or a minor-version interpreter mismatch, silently breaks the
copied `.venv` and the resolved wheels.

### III. Config-as-Environment (12-Factor)

Every runtime knob — `OPENAI_API_KEY`, `AUDIO_DIR`, `DB_PATH`, `HOST`, `PORT`, optional auth
credentials, and `STORAGE_BACKEND` — MUST be read from the environment. A single built image
MUST run unchanged locally, in Docker, and on a VPS. Required configuration MUST be validated
at startup and fail fast (e.g. raise `ValueError` when `OPENAI_API_KEY` is absent) rather than
failing midway through a request.

**Rationale**: One image, any environment, is the deployment contract. Reading config from the
environment and failing fast turns misconfiguration into an immediate, obvious startup error
instead of a confusing runtime failure.

### IV. Secrets & Data Never in the Image

`.dockerignore` MUST exclude `.env`, `audio/`, `data/`, `echoquize.db`, `.venv/`, and `.git/`.
Secrets MUST be injected at runtime via Compose `env_file`, never baked in through `COPY` or
`ENV` in the Dockerfile. The runtime container MUST run as a non-root user (uid 999).

**Rationale**: Anything copied into an image layer is effectively published and permanent.
Baking the API key or local audio into layers leaks credentials and bloats the image; runtime
injection plus a non-root user keeps the blast radius small.

### V. Durable Persistence

Generated audio files and the SQLite database MUST live on a host-visible bind-mounted volume
so they survive container rebuilds and remain inspectable on the host filesystem. SQLite MUST
reside on a real local filesystem and MUST use `check_same_thread=False` with an in-process
threading lock for concurrent-tab safety. `docker compose down` MUST NOT destroy persistent
data; running `docker compose down -v` (or any volume-deleting operation) is forbidden without
explicit, case-by-case user confirmation.

**Rationale**: The library's value is that it persists. Bind mounts on local disk keep data
visible and safe across rebuilds; SQLite file locking misbehaves on networked/overlay
filesystems, and `-v` is the one command that silently discards everything.

### VI. Pragmatic Single-User Scope

Echoquize is a personal, single-user tool. The simplest solution that works at single-user
scale MUST be preferred. An automated test suite is NOT required; per-sprint validation is
manual (browser tests and REPL one-liners as defined in each sprint). Additional complexity —
pytest suites, job queues, multi-user concurrency, horizontal scaling — MUST NOT be added
speculatively; it is justified only by a demonstrated, present need (YAGNI).

**Rationale**: Effort spent hardening for scale this tool will never see is effort stolen from
shipping features the single user actually wants. Complexity must earn its place.

### VII. Graceful, User-Facing Error Handling

API and input errors — rate limits, authentication failures, empty or over-length text
(> 4096 chars), and unsupported tag formats (PCM raw bytes, raw ADTS AAC) — MUST surface as
clear, human-readable status messages, never as raw tracebacks. Generation MUST degrade
gracefully (e.g. skip tag writing and warn, offer download-only when inline preview is
impossible) rather than blocking the user outright.

**Rationale**: A self-hosted tool with no support team must explain its own failures. A
friendly status line turns a dead end into a recoverable step; a traceback turns away the only
user there is.

## Technology & Deployment Constraints

- **Stack**: Python 3.12 (managed by uv), Gradio 6.x (Blocks layout), openai SDK 2.x, SQLite
  (stdlib), python-dotenv, mutagen. Resolve to the newest compatible releases, pinned via
  `uv.lock` (Principle II).
- **Packaging**: Multi-stage Docker build following Astral's official uv pattern — uv image in
  the builder stage, plain `python:3.12-slim-bookworm` (no uv binary) in the runtime stage.
- **Runtime**: Docker Compose with `restart: unless-stopped` for process supervision; Gradio
  MUST bind `0.0.0.0` inside the container (`HOST` defaults to `0.0.0.0`) and MUST NOT be
  overridden to `127.0.0.1`/`localhost`, which is unreachable from outside the container.
- **Tag-format reality**: tag support is format-dependent (ID3 for mp3/wav, VorbisComment for
  flac, OpusTags for opus); PCM and raw ADTS AAC are explicitly unsupported and MUST be handled
  per Principle VII, not silently failed.

## Development Workflow & Quality Gates

- **Spec Kit flow**: Features proceed through `/speckit.specify` → `/speckit.plan` →
  `/speckit.tasks` → `/speckit.implement`. Each plan's Constitution Check gate MUST evaluate the
  feature against the seven principles above before Phase 0 research and again after Phase 1
  design.
- **Validation over tests**: Each sprint defines its own demo/validation steps (Principle VI).
  A task is "done" only when its stated observable behavior is demonstrated — "the file contains
  X" is never sufficient evidence; predict and observe what actually happens.
- **Reproducibility gate**: Any dependency change MUST be accompanied by an updated, committed
  `uv.lock` produced by uv (not hand-edited).
- **Data-safety gate**: Any change touching Docker volumes, `compose.yml`, or teardown commands
  MUST preserve persistent data by default and call out destructive operations explicitly
  (Principle V).

## Governance

This constitution supersedes ad-hoc practice for the Echoquize project. When guidance here
conflicts with convenience, this document wins.

- **Amendments**: Changes to principles or governance MUST be made by editing this file,
  accompanied by a Sync Impact Report (the HTML comment at the top) and a version bump.
- **Versioning policy** (semantic):
  - **MAJOR** — backward-incompatible governance changes, or removal/redefinition of a
    principle.
  - **MINOR** — a new principle or materially expanded section is added.
  - **PATCH** — clarifications, wording, or non-semantic refinements.
- **Compliance review**: Every plan and implementation MUST be checked against these principles
  via the plan template's Constitution Check. Deviations MUST be recorded in that plan's
  Complexity Tracking table with explicit justification and the rejected simpler alternative;
  unjustified complexity is grounds to send the work back.
- **Runtime guidance**: Project- and agent-level operating instructions live in `CLAUDE.md` and
  the current plan under `context/`; this constitution governs the *rules*, those documents
  govern the *how-to*.

**Version**: 1.0.0 | **Ratified**: 2026-06-08 | **Last Amended**: 2026-06-08
