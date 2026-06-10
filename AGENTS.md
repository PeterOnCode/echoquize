<!-- SPECKIT START -->

## Active feature: 002-studio-enhancements (TTS Studio Enhancements)

Read the current plan and its design artifacts before working on this feature:

- Plan: `specs/002-studio-enhancements/plan.md` (stack, structure, Constitution Check)
- Spec: `specs/002-studio-enhancements/spec.md` (US1–US9, FR-001–048, SC-001–010)
- Research: `specs/002-studio-enhancements/research.md` (resolved technical decisions R1–R11)
- Data model: `specs/002-studio-enhancements/data-model.md`
- Contracts: `specs/002-studio-enhancements/contracts/` (naming, version, storage-backend, tag-writer, database, config, ui)
- Validation: `specs/002-studio-enhancements/quickstart.md`

Stack: Python 3.12 (uv), Gradio 6.x, openai SDK 2.x, python-dotenv, mutagen, SQLite; Docker
(multi-stage uv) + Compose with a `./data` bind mount. Governed by the constitution at
`.specify/memory/constitution.md` (v1.0.0) — storage abstraction, pinned/reproducible builds,
config-as-environment, secrets-never-in-image, durable persistence, pragmatic single-user scope,
graceful errors.<!-- SPECKIT END -->
