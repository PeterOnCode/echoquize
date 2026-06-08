# Contracts: Echoquize

**Date**: 2026-06-08 | **Feature**: 001-echoquize-tts

Echoquize exposes no external HTTP API — it is a self-contained Gradio app. The meaningful contracts
are its **internal module boundaries**, which the constitution depends on (especially the storage
abstraction, Principle I). Each file below pins a module's public interface: signatures,
input domains, return values, error behavior, and the guarantees callers may rely on.

| Contract | Module | Why it matters |
|----------|--------|----------------|
| [config.md](./config.md) | `config.py` | Config-as-environment + fail-fast (Principle III) |
| [tts-client.md](./tts-client.md) | `src/tts/client.py` | TTS call + graceful errors (Principle VII) |
| [storage-backend.md](./storage-backend.md) | `src/storage/` | Backend independence (Principle I) |
| [database.md](./database.md) | `src/db/database.py` | Persistence, pagination, bulk delete (Principle V) |
| [tag-writer.md](./tag-writer.md) | `src/tags/writer.py` | Format-aware tagging, unsupported-format handling |
| [ui-contract.md](./ui-contract.md) | `src/ui/`, `app.py` | UI surface, events, and user-facing behavior |

These contracts are the acceptance surface for `quickstart.md`: each validation scenario exercises
one or more of them and asserts the documented behavior.
