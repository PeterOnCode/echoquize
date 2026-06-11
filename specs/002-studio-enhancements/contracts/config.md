# Contract: Config (`config.py`, delta)

Adds optional default tag values (US7). All existing config (feature 001) is unchanged. No new
**required** config — the app starts with none of these set (Principle III; FR-048).

## New environment reads

| Env var | Type | Default | Maps to (tag) |
|---------|------|---------|---------------|
| `DEFAULT_TAG_ARTIST` | str | unset → `None` | artist |
| `DEFAULT_TAG_ALBUM` | str | unset → `None` | album |
| `DEFAULT_TAG_GENRE` | str | unset → `None` | genre |
| `DEFAULT_TAG_COMMENT` | str | unset → `None` | comment |
| `DEFAULT_TAG_LANGUAGE` | str | unset → `None` | languages (single seed value) |

Read with the existing `_get_env()` helper (same precedence rules as other knobs).

## Exposed value

```python
DEFAULT_TAGS: dict[str, str]   # only keys whose env var is set & non-empty are present
```

- Built from the reads above; an unset/blank var contributes **no key** (so consumers see "no
  default" rather than an empty string forced into the field).
- `title` is intentionally **not** part of `DEFAULT_TAGS` (FR-047).

**Guarantees**:

- Reading or building `DEFAULT_TAGS` never raises; a malformed value degrades to "unset" (blank
  field), never a startup error (FR-048).

**Consumers**: `src/ui/generate_tab.py` uses `DEFAULT_TAGS` to initialize the Generate form's tag
widgets and to seed the tags of newly added queue items (manual and file-upload). Users can
override or clear any pre-filled value before generating (FR-044–FR-046).

**Docs**: `.env.example` gains commented entries for each `DEFAULT_TAG_*` key.
