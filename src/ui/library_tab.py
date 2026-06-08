"""Library tab: browse, paginate, filter, preview, delete. See contracts/ui-contract.md."""

import gradio as gr

from src.db.database import (
    bulk_delete,
    count_generations,
    delete_generation,
    list_generations,
)
from src.storage import get_storage

PAGE_SIZE = 50
VOICE_CHOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
]
FILTER_CHOICES = ["All"] + VOICE_CHOICES
HEADERS = ["ID", "Created", "Voice", "Model", "Format", "Speed", "Text", "Size"]
NO_PREVIEW = {"pcm"}


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


def _on_select(records, evt: gr.SelectData):
    idx = evt.index[0]
    if records and 0 <= idx < len(records):
        rec = records[idx]
        preview = None if rec["format"] in NO_PREVIEW else get_storage().get_url(rec["file_path"])
        return rec["id"], preview
    return None, None


def _delete_selected(selected_id, page, voice_filter):
    view, info, records, page = reload_page(page, voice_filter)
    if not selected_id:
        return view, info, records, page, "❌ Select a row first."
    path = delete_generation(selected_id)
    if path:
        get_storage().delete(path)
    view, info, records, page = reload_page(page, voice_filter)
    return view, info, records, page, "✅ Deleted."


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
    paths = bulk_delete(voice=_voice_arg(bulk_voice), date_from=df_, date_to=dt)
    storage = get_storage()
    for p in paths:
        storage.delete(p)
    view, info, records, page = reload_page(0, voice_filter)
    return view, info, records, page, f"✅ Bulk-deleted {len(paths)} item(s)."


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

        df.select(_on_select, inputs=records_state, outputs=[selected_id, audio_preview])
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
