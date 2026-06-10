"""Library tab: browse, paginate, filter, preview, edit details, delete. See contracts/ui-contract.md."""

import json
import os

import gradio as gr

from src.db.database import (
    bulk_delete,
    count_generations,
    delete_generation,
    get_generation,
    list_generations,
    update_file_path,
    update_tags,
)
from src.naming import slugify
from src.storage import get_storage
from src.tags.writer import TagsNotSupportedError, write_tags
from src.ui.tag_fields import collect_tags, empty_tags, tags_to_fields

PAGE_SIZE = 50
VOICE_CHOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
]
FILTER_CHOICES = ["All"] + VOICE_CHOICES
HEADERS = ["ID", "Created", "Voice", "Model", "Format", "Speed", "Text", "Size"]
NO_PREVIEW = {"pcm"}
NO_TAGS = {"pcm", "aac"}  # no usable tag container (FR-014)

# 16 tag fields cleared on row deselect / clear.
_BLANK_TAGS = tags_to_fields(empty_tags())


def _voice_arg(voice_filter):
    return None if voice_filter in (None, "All") else voice_filter


def _fmt_size(n):
    return f"{n / 1024:.1f} KB" if n else ""


def _records_to_view(records):
    return [
        [
            r["id"][:8], (r["created_at"] or "")[:19], r["voice"], r["model"],
            r["format"], r["speed"], (r["text_input"] or "")[:60], _fmt_size(r["file_size"]),
        ]
        for r in records
    ]


def reload_page(page, voice_filter):
    """Return (view, info, records, clamped_page) for the requested page."""
    voice = _voice_arg(voice_filter)
    total = count_generations(voice)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(int(page or 0), pages - 1))
    records = list_generations(limit=PAGE_SIZE, offset=page * PAGE_SIZE, voice=voice)
    info = f"Page {page + 1} / {pages} — {total} item(s)"
    return _records_to_view(records), info, records, page


def _file_size(path):
    """On-disk size for a local file, or None if it can't be measured (remote backend)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _record_to_tags(rec):
    """Reconstruct the expanded tag dict from a generation record's columns + tags_extra."""
    extra = {}
    raw = rec.get("tags_extra")
    if raw:
        try:
            extra = json.loads(raw)
        except (ValueError, TypeError):
            extra = {}
    tags = empty_tags()
    tags.update({
        "title": rec.get("tag_title") or "",
        "artist": rec.get("tag_artist") or "",
        "album": rec.get("tag_album") or "",
        "genre": rec.get("tag_genre") or "",
        "comment": rec.get("tag_comment") or "",
        "date": rec.get("tag_year") or "",
        "track": rec.get("tag_track") or "",
        "languages": extra.get("languages") or [],
        "custom_text": extra.get("custom_text") or [],
        "custom_url": extra.get("custom_url") or [],
    })
    return tags


def _on_select(records, evt: gr.SelectData):
    """Row select → (id, preview, filename stem, extension, 16 tag fields, notice)."""
    idx = evt.index[0]
    if records and 0 <= idx < len(records):
        rec = records[idx]
        fmt = rec["format"]
        preview = None if fmt in NO_PREVIEW else get_storage().get_url(rec["file_path"])
        stem, ext = os.path.splitext(os.path.basename(rec["file_path"]))
        notice = (f"Editing {os.path.basename(rec['file_path'])}."
                  + ("" if fmt not in NO_TAGS else f" Tags aren't supported for {fmt} — only the filename will change."))
        return (rec["id"], preview, stem, ext, *tags_to_fields(_record_to_tags(rec)), notice)
    return (None, None, "", "", *_BLANK_TAGS, "Select a row to edit it.")


def _save_details(selected_id, page, voice_filter, stem_input,
                  title, artist, album, genre, date, track, languages, comment,
                  ct1_desc, ct1_val, ct2_desc, ct2_val,
                  cu1_desc, cu1_val, cu2_desc, cu2_val):
    """Rename the file (if the stem changed) and write the expanded tags (US5)."""
    if not selected_id:
        status = "❌ Select a row first."
    else:
        rec = get_generation(selected_id)
        if not rec:
            status = "❌ That item no longer exists."
        else:
            tags = collect_tags(title, artist, album, genre, date, track, languages, comment,
                                ct1_desc, ct1_val, ct2_desc, ct2_val,
                                cu1_desc, cu1_val, cu2_desc, cu2_val)
            status = _apply_details(selected_id, rec, stem_input, tags)
    view, info, records, page = reload_page(page, voice_filter)
    return view, info, records, page, status


def _apply_details(gid, rec, stem_input, tags):
    """Do the rename + tag write for one record; return a friendly status string."""
    fmt = rec["format"]
    old_path = rec["file_path"]
    cur_stem, ext = os.path.splitext(os.path.basename(old_path))
    target_path = old_path
    msgs = []

    desired = (stem_input or "").strip()
    if not desired:
        msgs.append("empty filename ignored — kept original")
    elif desired != cur_stem:
        slug = slugify(desired)
        if not slug:
            msgs.append("filename has no usable characters — kept original")
        else:
            try:
                target_path = get_storage().rename(old_path, f"{slug}{ext}")
                update_file_path(gid, target_path)
                msgs.append(f"renamed to {os.path.basename(target_path)}")
            except FileNotFoundError:
                return "❌ The file is missing — nothing changed."
            except NotImplementedError:
                msgs.append("rename not supported by this storage backend")
            except Exception as exc:  # never leak a traceback
                msgs.append(f"rename failed ({type(exc).__name__})")

    try:
        write_tags(target_path, fmt, tags)
        update_tags(gid, tags, file_size=_file_size(target_path))
        msgs.append("tags saved")
    except TagsNotSupportedError:
        msgs.append(f"tags skipped ({fmt} can't carry tags)")
    except Exception as exc:  # never leak a traceback
        msgs.append(f"tags not written ({type(exc).__name__})")

    return "✅ " + "; ".join(msgs) + "."


def _clear_tags(selected_id, page, voice_filter):
    """Strip tags from the file + record (filename unchanged); blank the tag fields."""
    status = "✅ Tags cleared."
    if not selected_id:
        status = "❌ Select a row first."
    else:
        rec = get_generation(selected_id)
        if not rec:
            status = "❌ That item no longer exists."
        else:
            empty = empty_tags()
            try:
                write_tags(rec["file_path"], rec["format"], empty)
                update_tags(selected_id, empty, file_size=_file_size(rec["file_path"]))
            except TagsNotSupportedError:
                update_tags(selected_id, empty)  # no file tags; just clear the record
            except Exception as exc:
                status = f"❌ Could not clear file tags ({type(exc).__name__})."
    view, info, records, page = reload_page(page, voice_filter)
    return (*_BLANK_TAGS, view, info, records, page, status)


def _delete_selected(selected_id, page, voice_filter):
    if not selected_id:
        view, info, records, page = reload_page(page, voice_filter)
        return view, info, records, page, "❌ Select a row first."
    try:
        path = delete_generation(selected_id)
        if path:
            get_storage().delete(path)
        status = "✅ Deleted."
    except Exception as exc:  # never leak a traceback to the user
        status = f"❌ Failed to delete ({type(exc).__name__})."
    view, info, records, page = reload_page(page, voice_filter)
    return view, info, records, page, status


def _norm_dates(date_from, date_to):
    df_ = (date_from or "").strip() or None
    dt = (date_to or "").strip() or None
    if dt and len(dt) == 10:  # date-only → make end-of-day inclusive
        dt = dt + "T23:59:59.999999"
    return df_, dt


def _bulk_clean(confirm, bulk_voice, date_from, date_to, voice_filter):
    if not confirm:
        view, info, records, page = reload_page(0, voice_filter)
        return view, info, records, page, "❌ Tick 'Confirm' before bulk-deleting."
    df_, dt = _norm_dates(date_from, date_to)
    try:
        paths = bulk_delete(voice=_voice_arg(bulk_voice), date_from=df_, date_to=dt)
        storage = get_storage()
        for p in paths:
            storage.delete(p)
        status = f"✅ Bulk-deleted {len(paths)} item(s)."
    except Exception as exc:  # never leak a traceback to the user
        status = f"❌ Bulk delete failed ({type(exc).__name__})."
    view, info, records, page = reload_page(0, voice_filter)
    return view, info, records, page, status


def build_library_tab():
    """Build the Library tab; return reload handle + io for app-level refresh."""
    with gr.Tab("Library"):
        page_state = gr.State(0)
        records_state = gr.State([])
        selected_id = gr.State(None)

        with gr.Row():
            voice_filter = gr.Dropdown(label="Filter by voice", choices=FILTER_CHOICES, value="All")
            refresh_btn = gr.Button("Refresh")
            prev_btn = gr.Button("← Prev")
            next_btn = gr.Button("Next →")
        info = gr.Markdown("")
        df = gr.Dataframe(headers=HEADERS, interactive=False, wrap=True)
        audio_preview = gr.Audio(label="Preview selected", type="filepath")

        with gr.Accordion("Edit details", open=False):
            tag_notice = gr.Markdown("Select a row to edit its filename and tags.")
            with gr.Row():
                e_filename = gr.Textbox(label="Filename", max_lines=1)
                e_ext = gr.Textbox(label="Extension", max_lines=1, interactive=False)
            with gr.Row():
                e_title = gr.Textbox(label="Title", max_lines=1)
                e_artist = gr.Textbox(label="Artist", max_lines=1)
            with gr.Row():
                e_album = gr.Textbox(label="Album", max_lines=1)
                e_genre = gr.Textbox(label="Genre", max_lines=1)
            with gr.Row():
                e_date = gr.Textbox(label="Recording date (YYYY or YYYY-MM-DD)", max_lines=1)
                e_track = gr.Textbox(label="Track (n or n/total)", max_lines=1)
            with gr.Row():
                e_languages = gr.Textbox(label="Language(s) — comma-separated", max_lines=1)
                e_comment = gr.Textbox(label="Comment", max_lines=1)
            with gr.Accordion("Custom fields", open=False):
                with gr.Row():
                    e_ct1_desc = gr.Textbox(label="Custom text 1 — name", max_lines=1)
                    e_ct1_val = gr.Textbox(label="Custom text 1 — value", max_lines=1)
                with gr.Row():
                    e_ct2_desc = gr.Textbox(label="Custom text 2 — name", max_lines=1)
                    e_ct2_val = gr.Textbox(label="Custom text 2 — value", max_lines=1)
                with gr.Row():
                    e_cu1_desc = gr.Textbox(label="Custom URL 1 — name", max_lines=1)
                    e_cu1_val = gr.Textbox(label="Custom URL 1 — URL", max_lines=1)
                with gr.Row():
                    e_cu2_desc = gr.Textbox(label="Custom URL 2 — name", max_lines=1)
                    e_cu2_val = gr.Textbox(label="Custom URL 2 — URL", max_lines=1)
            with gr.Row():
                save_btn = gr.Button("Save details", variant="primary")
                clear_tags_btn = gr.Button("Clear tags")

        with gr.Row():
            delete_btn = gr.Button("Delete selected", variant="stop")
        with gr.Accordion("Bulk cleanup", open=False):
            gr.Markdown("Delete many at once. Leave filters empty to match everything.")
            with gr.Row():
                bulk_voice = gr.Dropdown(label="Voice", choices=FILTER_CHOICES, value="All")
                date_from = gr.Textbox(label="From (YYYY-MM-DD)", max_lines=1)
                date_to = gr.Textbox(label="To (YYYY-MM-DD)", max_lines=1)
            confirm = gr.Checkbox(label="Confirm bulk delete (records + files)", value=False)
            bulk_btn = gr.Button("Bulk delete", variant="stop")
        status = gr.Textbox(label="Status", interactive=False)

        page_outputs = [df, info, records_state, page_state]
        tag_fields = [
            e_title, e_artist, e_album, e_genre, e_date, e_track, e_languages, e_comment,
            e_ct1_desc, e_ct1_val, e_ct2_desc, e_ct2_val, e_cu1_desc, e_cu1_val, e_cu2_desc, e_cu2_val,
        ]

        refresh_btn.click(reload_page, [page_state, voice_filter], page_outputs)
        voice_filter.change(lambda v: reload_page(0, v), voice_filter, page_outputs)
        prev_btn.click(lambda p, v: reload_page((p or 0) - 1, v), [page_state, voice_filter], page_outputs)
        next_btn.click(lambda p, v: reload_page((p or 0) + 1, v), [page_state, voice_filter], page_outputs)

        df.select(
            _on_select,
            inputs=records_state,
            outputs=[selected_id, audio_preview, e_filename, e_ext, *tag_fields, tag_notice],
        )
        save_btn.click(
            _save_details,
            [selected_id, page_state, voice_filter, e_filename, *tag_fields],
            page_outputs + [status],
        )
        clear_tags_btn.click(
            _clear_tags,
            [selected_id, page_state, voice_filter],
            tag_fields + page_outputs + [status],
        )
        delete_btn.click(
            _delete_selected, [selected_id, page_state, voice_filter], page_outputs + [status]
        )
        bulk_btn.click(
            _bulk_clean,
            [confirm, bulk_voice, date_from, date_to, voice_filter],
            page_outputs + [status],
        )

    return {
        "reload": reload_page,
        "inputs": [page_state, voice_filter],
        "outputs": page_outputs,
    }
