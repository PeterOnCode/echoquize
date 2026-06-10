# Contract: Storage Backend (`src/storage/*`, delta)

Extends the feature-001 `StorageBackend` ABC + `get_storage()` factory. **Principle I is the
binding rule**: all folder-layout knowledge, collision resolution, and renaming live *inside*
backends. Callers pass a desired filename/stem and receive the actual stored path; they never build
`YYYY/MM/DD` paths, list directories, or move files themselves.

## Layout change (US6)

The path/key convention changes from `…/YYYY/MM/<filename>` to `…/YYYY/MM/DD/<filename>`, where
`YYYY/MM/DD` is derived from the current UTC time. Applies uniformly to every backend (FR-021,
FR-022). Existing files under the old layout are **not** moved; they continue to be read at their
stored `file_path` (FR-024).

## `save(data: bytes, filename: str) -> str` (now collision-safe)

Unchanged signature. New behavior: if `filename` would collide with an existing object in the
computed target (dated) folder, the backend appends a numeric suffix to the **stem** (`_2`, `_3`,
…), keeping the whole stem ≤ 64 characters, and stores under the unique name. Returns the **actual**
stored path/key.

- Callers pass `f"{stem}.{ext}"` where `stem` comes from `naming.slugify(title)` or a UUID
  fallback. UUID stems never collide, so suffixing is exercised only by slug names.
- A title/stem MUST NOT overwrite an existing file (FR-017).

## `rename(old_path: str, new_filename: str) -> str` (NEW abstract method)

Move/rename the existing object at `old_path` to `new_filename` **within the same dated folder**,
collision-safe (same `_2`/`_3` rule and 64-char cap as `save()`), and return the new path/key.

- `new_filename` is `f"{stem}.{ext}"`; the extension MUST match the original (callers keep it fixed,
  FR-042).
- On collision, append a suffix and return the final name (caller reports it to the user, FR-040).
- If the source object is missing, raise an error the caller can surface as a friendly message
  (the caller leaves the record unchanged).
- Updates only storage; the caller updates the DB `file_path` via `update_file_path()`.

### Backend implementations

| Backend | `save()` collision | `rename()` |
|---------|-------------------|-----------|
| `LocalStorage` | check `path.exists()` in the `YYYY/MM/DD` subdir, suffix stem until free, write | `os.replace`/move within the source file's directory, suffix until free, return new path |
| `S3Storage` (stub) | n/a (stub `save` already raises) | raise `NotImplementedError` |
| `GDriveStorage` (stub) | n/a | raise `NotImplementedError` |

Adding `rename()` to the ABC means every concrete backend must define it; the stubs define it as a
`NotImplementedError` raiser, mirroring their existing `save()` stubs (so the package stays
importable and instantiation only fails when actually selected).

## `delete(path)` / `get_url(path)`

Unchanged.

**Guarantees**:

- No caller outside `src/storage/` references `YYYY/MM/DD`, lists a directory, or moves a file.
- `save()` and `rename()` always return a path that exists and is unique within its dated folder.
