<!-- SPECKIT START -->
## Active feature: 001-echoquize-tts (Echoquize — Self-Hosted Text-to-Speech Studio)

Read the current plan and its design artifacts before working on this feature:

- Plan: `specs/001-echoquize-tts/plan.md` (stack, structure, Constitution Check)
- Spec: `specs/001-echoquize-tts/spec.md` (US1–US5, FR-001–024, SC-001–009)
- Research: `specs/001-echoquize-tts/research.md` (resolved technical decisions D1–D13)
- Data model: `specs/001-echoquize-tts/data-model.md`
- Contracts: `specs/001-echoquize-tts/contracts/` (config, tts-client, storage-backend, database, tag-writer, ui)
- Validation: `specs/001-echoquize-tts/quickstart.md`

Stack: Python 3.12 (uv), Gradio 6.x, openai SDK 2.x, python-dotenv, mutagen, SQLite; Docker
(multi-stage uv) + Compose with a `./data` bind mount. Governed by the constitution at
`.specify/memory/constitution.md` (v1.0.0) — storage abstraction, pinned/reproducible builds,
config-as-environment, secrets-never-in-image, durable persistence, pragmatic single-user scope,
graceful errors.
<!-- SPECKIT END -->
