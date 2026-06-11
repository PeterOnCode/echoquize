"""Shared audio-tag form helpers used by the Generate and Library tabs.

Converts between the flat UI fields and the expanded logical tag dict (see
specs/002-studio-enhancements/contracts/tag-writer.md). Custom text/URL use a
fixed two-row layout; ``languages`` is a comma-separated string.
"""


def empty_tags() -> dict:
    """A complete, empty expanded-tag dict (every field present)."""
    return {
        "title": "", "artist": "", "album": "", "genre": "", "comment": "",
        "date": "", "track": "", "languages": [], "custom_text": [], "custom_url": [],
    }


def collect_tags(title, artist, album, genre, date, track, languages, comment,
                 ct1_desc, ct1_val, ct2_desc, ct2_val,
                 cu1_desc, cu1_val, cu2_desc, cu2_val) -> dict:
    """Build the expanded logical tag dict from the flat form fields."""
    def _s(v):
        return (v or "").strip()

    langs = [x.strip() for x in (languages or "").split(",") if x.strip()]
    custom_text = [
        {"desc": _s(d), "value": _s(v)}
        for d, v in ((ct1_desc, ct1_val), (ct2_desc, ct2_val))
        if _s(v)
    ]
    custom_url = [
        {"desc": _s(d), "url": _s(v)}
        for d, v in ((cu1_desc, cu1_val), (cu2_desc, cu2_val))
        if _s(v)
    ]
    return {
        "title": _s(title), "artist": _s(artist), "album": _s(album),
        "genre": _s(genre), "comment": _s(comment),
        "date": _s(date), "track": _s(track),
        "languages": langs, "custom_text": custom_text, "custom_url": custom_url,
    }


def tags_to_fields(tags) -> tuple:
    """Expand a tag dict into the flat field values (inverse of collect_tags)."""
    t = tags or empty_tags()
    ct = (list(t.get("custom_text") or []) + [{}, {}])[:2]
    cu = (list(t.get("custom_url") or []) + [{}, {}])[:2]
    return (
        t.get("title", ""), t.get("artist", ""), t.get("album", ""), t.get("genre", ""),
        t.get("date", ""), t.get("track", ""), ", ".join(t.get("languages") or []),
        t.get("comment", ""),
        ct[0].get("desc", ""), ct[0].get("value", ""),
        ct[1].get("desc", ""), ct[1].get("value", ""),
        cu[0].get("desc", ""), cu[0].get("url", ""),
        cu[1].get("desc", ""), cu[1].get("url", ""),
    )
