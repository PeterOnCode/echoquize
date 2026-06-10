# Contracts: TTS Studio Enhancements (002)

These contracts describe **deltas** to the feature-001 module interfaces. Anything not mentioned
here is unchanged from `specs/001-echoquize-tts/contracts/`.

| Contract | Module | Stories | Summary |
|----------|--------|---------|---------|
| [naming.md](./naming.md) | `src/naming.py` (new) | US3, US4, US5 | `slugify()` title → filename stem |
| [version.md](./version.md) | `src/version.py` (new) | US8 | `app_version()` from `pyproject.toml` |
| [storage-backend.md](./storage-backend.md) | `src/storage/*` | US3, US4, US5 | `YYYY/MM/DD`, collision-safe `save()`, new `rename()` |
| [tag-writer.md](./tag-writer.md) | `src/tags/writer.py` | US2 | expanded ID3v2.4.0 frame set + Vorbis mapping |
| [database.md](./database.md) | `src/db/database.py` | US2, US5 | new columns, migration, `update_file_path()` |
| [config.md](./config.md) | `config.py` | US7 | `DEFAULT_TAGS` from environment |
| [ui-contract.md](./ui-contract.md) | `app.py`, `src/ui/*` | US1, US2, US3, US5, US7, US8 | UI behavior deltas |

Tooling (US6/US9, `pyproject.toml` + `justfile`) is covered in [research.md](../research.md) R7 and
the plan; it has no runtime module interface.

**Verification standard** (constitution): a contract is satisfied only when its observable behavior
is demonstrated, not when "the file contains X". See [quickstart.md](../quickstart.md).
