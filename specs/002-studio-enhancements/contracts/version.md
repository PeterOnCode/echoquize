# Contract: Version (`src/version.py`, new)

Single source of truth for the app version shown in the UI (US8). Pure read; no config, no network.

## `app_version() -> str | None`

Return the project version string (e.g. `"0.1.0"`), or `None` if it cannot be determined.

**Resolution order**:

1. `importlib.metadata.version("echoquize")` — works only if the project is installed as a
   distribution.
2. Fallback: read `[project].version` from `pyproject.toml` (resolved relative to the repo root)
   using stdlib `tomllib`.
3. On any failure (file missing, key absent, parse error): return `None`.

**Guarantees**:

- Never raises — a missing/garbled source yields `None`, not an exception (FR-026: the app must
  never fail at startup because of version display).
- Read at runtime, so a `bump-my-version` bump of `[project].version` is reflected with no code
  change (FR-030).

**Consumer** (`app.py`): renders `f"v{app_version()}"` as unobtrusive text next to the title when
non-`None`; renders nothing (or a neutral placeholder) when `None` (FR-025, FR-027 — display only,
no remote check).

> `pyproject.toml` currently has no `[build-system]`, so step 2 is the dependable path today; step 1
> is kept as a forward-compatible first try (R6).
