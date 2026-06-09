"""Library tab: browse, paginate, filter, preview, delete. See contracts/ui-contract.md."""

import os

import gradio as gr

from src.db.database import (
    bulk_delete,
    count_generations,
    delete_generation,
    get_generation,
    list_generations,
    update_tags,
)
from src.storage import get_storage
from src.tags.writer import TagsNotSupportedError, write_tags

PAGE_SIZE = 50
VOICE_CHOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
]
FILTER_CHOICES = ["All"] + VOICE_CHOICES
HEADERS = ["ID", "Created", "Voice", "Model", "Format", "Speed", "Text", "Size"]
NO_PREVIEW = {"pcm"}
NO_TAGS = {"pcm", "aac"}  # no usable tag container (FR-014)


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


_EMPTY_TAG_FIELDS = ("", "", "", "", "", "")


def _on_select(records, evt: gr.SelectData):
    """Row select → (id, preview, 6 tag fields, save-enabled update, tag notice)."""
    idx = evt.index[0]
    if records and 0 <= idx < len(records):
        rec = records[idx]
        fmt = rec["format"]
        preview = None if fmt in NO_PREVIEW else get_storage().get_url(rec["file_path"])
        taggable = fmt not in NO_TAGS
        notice = "" if taggable else f"Tags are not supported for {fmt} — saving disabled."
        return (
            rec["id"], preview,
            rec.get("tag_title") or "", rec.get("tag_artist") or "",
            rec.get("tag_album") or "", rec.get("tag_comment") or "",
            rec.get("tag_genre") or "", rec.get("tag_year") or "",
            gr.update(interactive=taggable), notice,
        )
    return (None, None, *_EMPTY_TAG_FIELDS, gr.update(interactive=False), "")


def _tags_dict(title, artist, album, comment, genre, year):
    return {
        "title": title, "artist": artist, "album": album,
        "comment": comment, "genre": genre, "year": year,
    }


def _file_size(path):
    """On-disk size for a local file, or None if it can't be measured (remote backend)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _save_tags(selected_id, page, voice_filter, title, artist, album, comment, genre, year):
    """Write tags to the file + record, then reload so records_state is fresh."""
    status = "✅ Tags saved."
    if not selected_id:
        status = "❌ Select a row first."
    else:
        rec = get_generation(selected_id)
        if not rec:
            status = "❌ That item no longer exists."
        else:
            tags = _tags_dict(title, artist, album, comment, genre, year)
            try:
                write_tags(rec["file_path"], rec["format"], tags)
                update_tags(selected_id, tags, file_size=_file_size(rec["file_path"]))
            except TagsNotSupportedError:
                status = f"❌ Tags are not supported for {rec['format']}."
            except Exception as exc:  # never leak a traceback to the user
                status = f"❌ Could not write tags ({type(exc).__name__})."
    view, info, records, page = reload_page(page, voice_filter)
    return view, info, records, page, status


def _clear_tags(selected_id, page, voice_filter):
    """Strip tags from the file and record, blank the fields, and reload state."""
    status = "✅ Tags cleared."
    if not selected_id:
        status = "❌ Select a row first."
    else:
        rec = get_generation(selected_id)
        if not rec:
            status = "❌ That item no longer exists."
        else:
            empty = _tags_dict("", "", "", "", "", "")
            try:
                write_tags(rec["file_path"], rec["format"], empty)
                update_tags(selected_id, empty, file_size=_file_size(rec["file_path"]))
            except TagsNotSupportedError:
                update_tags(selected_id, empty)  # no file tags; just clear the record
            except Exception as exc:
                status = f"❌ Could not clear file tags ({type(exc).__name__})."
    view, info, records, page = reload_page(page, voice_filter)
    return (*_EMPTY_TAG_FIELDS, view, info, records, page, status)


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

        with gr.Accordion("Edit tags", open=False):
            tag_notice = gr.Markdown("Select a row to edit its tags.")
            with gr.Row():
                e_title = gr.Textbox(label="Title", max_lines=1)
                e_artist = gr.Textbox(label="Artist", max_lines=1)
            with gr.Row():
                e_album = gr.Textbox(label="Album", max_lines=1)
                e_genre = gr.Textbox(label="Genre", max_lines=1)
            with gr.Row():
                e_year = gr.Textbox(label="Year", max_lines=1)
                e_comment = gr.Textbox(label="Comment", max_lines=1)
            with gr.Row():
                save_tags_btn = gr.Button("Save tags", variant="primary")
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

        refresh_btn.click(reload_page, [page_state, voice_filter], page_outputs)
        voice_filter.change(lambda v: reload_page(0, v), voice_filter, page_outputs)
        prev_btn.click(lambda p, v: reload_page((p or 0) - 1, v), [page_state, voice_filter], page_outputs)
        next_btn.click(lambda p, v: reload_page((p or 0) + 1, v), [page_state, voice_filter], page_outputs)

        df.select(
            _on_select,
            inputs=records_state,
            outputs=[
                selected_id, audio_preview,
                e_title, e_artist, e_album, e_comment, e_genre, e_year,
                save_tags_btn, tag_notice,
            ],
        )
        save_tags_btn.click(
            _save_tags,
            [selected_id, page_state, voice_filter,
             e_title, e_artist, e_album, e_comment, e_genre, e_year],
            page_outputs + [status],
        )
        clear_tags_btn.click(
            _clear_tags,
            [selected_id, page_state, voice_filter],
            [e_title, e_artist, e_album, e_comment, e_genre, e_year] + page_outputs + [status],
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
