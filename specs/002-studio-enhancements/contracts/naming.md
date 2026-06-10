# Contract: Naming / Slug (`src/naming.py`, new)

Pure module — no I/O, no config, no storage knowledge. Shared by generation, batch, and Library
rename (US3, US4, US5).

## `slugify(title: str) -> str`

Produce a filesystem-safe filename **stem** (no extension) from a title.

**Algorithm** (in order):

1. Transliterate to ASCII: `unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()`.
2. Lowercase.
3. Replace any run of whitespace with a single `_`.
4. Remove every character not in `[a-z0-9_-]`.
5. Collapse any run of `_`/`-` to a single separator; strip leading/trailing separators.
6. Truncate to **64 characters** (after a truncation that lands on a separator, strip it again).

**Returns**: the stem, possibly `""` (empty) when the input has no ASCII-representable
alphanumerics (e.g. a non-Latin script, or emoji-only). Callers treat `""` as "no usable name" and
fall back to a UUID stem (generation) or reject the input (Library rename).

**Examples**:

| Input | Output |
|-------|--------|
| `"My Great Clip!"` | `my_great_clip` |
| `"Café déjà vu"` | `cafe_deja_vu` |
| `"  spaced  out  "` | `spaced_out` |
| `"日本語"` | `""` (empty → caller falls back) |
| 80-char title | first ≤64 chars of the slug |

**Guarantees**: deterministic; never returns a string with characters outside `[a-z0-9_-]`; never
returns a string > 64 chars; never raises on any `str` input (including `""`).

> Uniqueness/`_2` suffixing is **not** done here — that belongs to the storage backend, which knows
> the target folder (see [storage-backend.md](./storage-backend.md), Principle I).
