"""Generate tab: single + batch text-to-speech generation. See contracts/ui-contract.md."""

import os
import tempfile
import uuid
import zipfile

import gradio as gr

from src.db.database import insert_generation
from src.naming import slugify
from src.storage import get_storage
from src.tags.writer import TagsNotSupportedError, write_tags
from src.tts.client import MAX_CHARS, TTSError, generate_speech

VOICE_CHOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
]
MODEL_CHOICES = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]
FORMAT_CHOICES = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
NO_PREVIEW = {"pcm"}  # raw bytes — no inline player
NO_TAGS = {"pcm", "aac"}  # no usable tag container (FR-014)

QUEUE_HEADERS = ["#", "Text", "Voice", "Model", "Format", "Speed"]


# --------------------------------------------------------------------------- #
# Single generation
# --------------------------------------------------------------------------- #
def _collect_tags(title, artist, album, genre, date, track, languages, comment,
                  ct1_desc, ct1_val, ct2_desc, ct2_val,
                  cu1_desc, cu1_val, cu2_desc, cu2_val):
    """Build the expanded logical tag dict from the Generate-form fields (US2).

    ``languages`` is a comma-separated string; custom text/URL come in fixed
    (desc, value) pairs and are kept only when the value is non-empty.
    """
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


def _apply_tags(audio, fmt, tags):
    """Tag the raw audio *bytes* (via a temp file) before they reach storage.

    Returns ``(audio_bytes, status_note, written)``. Tagging bytes — not the stored
    path — keeps this correct for remote backends and keeps file_size in sync with
    the bytes actually saved. Never raises: a tag failure leaves the audio untagged
    rather than losing the generation (Principle VII).
    """
    has_any = any((
        tags["title"], tags["artist"], tags["album"], tags["genre"],
        tags["comment"], tags["date"], tags["track"],
        tags["languages"], tags["custom_text"], tags["custom_url"],
    ))
    if not has_any:
        return audio, "", False
    if fmt in NO_TAGS:
        return audio, f" Tags not supported for {fmt} — skipped.", False
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
            tmp.write(audio)
            tmp_path = tmp.name
        write_tags(tmp_path, fmt, tags)
        with open(tmp_path, "rb") as fh:
            data = fh.read()
        note = " Tags written."
        if tags["custom_url"] and fmt in ("flac", "opus"):
            note += f" (Custom URL isn't embedded for {fmt}.)"
        return data, note, True
    except TagsNotSupportedError:
        return audio, f" Tags not supported for {fmt} — skipped.", False
    except Exception as exc:  # never leak a traceback to the user
        return audio, f" Tags could not be written ({type(exc).__name__}).", False
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _tag_record_fields(tags, tagged):
    """Map the expanded tag dict to DB record fields — only when embedded.

    Persisting only embedded tags avoids phantom metadata for untaggable formats.
    """
    if not tagged:
        return {}
    extra = {
        key: value for key, value in (
            ("languages", tags["languages"]),
            ("custom_text", tags["custom_text"]),
            ("custom_url", tags["custom_url"]),
        ) if value
    }
    return {
        "tag_title": tags["title"] or None,
        "tag_artist": tags["artist"] or None,
        "tag_album": tags["album"] or None,
        "tag_comment": tags["comment"] or None,
        "tag_genre": tags["genre"] or None,
        "tag_year": tags["date"] or None,  # column reused for the recording date
        "tag_track": tags["track"] or None,
        "tags_extra": extra or None,
    }


def _on_generate(text, voice, model, fmt, speed, instructions,
                 t_title, t_artist, t_album, t_genre, t_date, t_track,
                 t_languages, t_comment,
                 ct1_desc, ct1_val, ct2_desc, ct2_val,
                 cu1_desc, cu1_val, cu2_desc, cu2_val):
    """Validate, synthesize, save, tag, persist; return (preview, download, status)."""
    text = (text or "").strip()
    if not text:
        return None, None, "❌ Text is required."
    if len(text) > MAX_CHARS:
        return None, None, f"❌ Text exceeds {MAX_CHARS} characters (got {len(text)})."

    tags = _collect_tags(t_title, t_artist, t_album, t_genre, t_date, t_track,
                         t_languages, t_comment,
                         ct1_desc, ct1_val, ct2_desc, ct2_val,
                         cu1_desc, cu1_val, cu2_desc, cu2_val)
    try:
        storage = get_storage()
        audio = generate_speech(text, model, voice, fmt, float(speed), instructions)
        audio, tag_note, tagged = _apply_tags(audio, fmt, tags)  # tag bytes before saving
        stem = slugify(tags["title"]) or uuid.uuid4().hex  # title-derived name, UUID fallback
        path = storage.save(audio, f"{stem}.{fmt}")
        record = {
            "text_input": text, "voice": voice, "model": model, "format": fmt,
            "speed": float(speed), "file_path": path, "file_size": len(audio),
        }
        record.update(_tag_record_fields(tags, tagged))  # only embedded tags persist
        gid = insert_generation(record)
        url = storage.get_url(path)  # locator for Gradio — never the raw backend path
    except TTSError as exc:
        return None, None, f"❌ {exc}"
    except Exception as exc:  # safety net — never leak a traceback to the user
        return None, None, f"❌ Unexpected error ({type(exc).__name__})."

    status = (
        f"✅ Generated {len(audio) / 1024:.1f} KB — saved as "
        f"{os.path.basename(path)} (id {gid[:8]})." + tag_note
    )
    if fmt in NO_PREVIEW:
        return None, url, status + " Inline preview is unavailable for PCM — download only."
    return url, url, status


# --------------------------------------------------------------------------- #
# Batch queue
# --------------------------------------------------------------------------- #
def _queue_view(queue):
    return [
        [
            i + 1,
            (q["text"][:40] + ("…" if len(q["text"]) > 40 else "")),
            q["voice"], q["model"], q["format"], q["speed"],
        ]
        for i, q in enumerate(queue)
    ]


def _empty_tags():
    """A complete, empty expanded-tag dict (every queue item carries one)."""
    return {
        "title": "", "artist": "", "album": "", "genre": "", "comment": "",
        "date": "", "track": "", "languages": [], "custom_text": [], "custom_url": [],
    }


def _tags_to_fields(tags):
    """Expand a tag dict into the flat edit-panel field values (inverse of _collect_tags)."""
    t = tags or _empty_tags()
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


def _add_to_queue(queue, text, voice, model, fmt, speed, instructions,
                  t_title, t_artist, t_album, t_genre, t_date, t_track,
                  t_languages, t_comment,
                  ct1_desc, ct1_val, ct2_desc, ct2_val,
                  cu1_desc, cu1_val, cu2_desc, cu2_val):
    queue = list(queue or [])
    text = (text or "").strip()
    if not text:
        return queue, _queue_view(queue), "❌ Enter text before adding to the queue."
    if len(text) > MAX_CHARS:
        return queue, _queue_view(queue), f"❌ Item exceeds {MAX_CHARS} characters."
    tags = _collect_tags(t_title, t_artist, t_album, t_genre, t_date, t_track,
                         t_languages, t_comment,
                         ct1_desc, ct1_val, ct2_desc, ct2_val,
                         cu1_desc, cu1_val, cu2_desc, cu2_val)
    queue.append(
        {
            "text": text, "voice": voice, "model": model, "format": fmt,
            "speed": float(speed), "instructions": instructions, "tags": tags,
        }
    )
    return queue, _queue_view(queue), f"Queued — {len(queue)} item(s)."


def _parse_upload(file_path: str):
    """Read a UTF-8 .txt file → ``(valid_lines, blank_count, rejected_line_numbers)``.

    Splits on newlines, trims each line, skips blank/whitespace-only lines, and
    rejects lines longer than ``MAX_CHARS`` (line numbers are 1-based). Parsing
    happens fully in memory before any API call, so even a large file only
    affects queue building, not generation (FR-002, FR-004, FR-006, FR-008).
    """
    with open(file_path, encoding="utf-8") as fh:
        content = fh.read()
    valid: list[str] = []
    blank = 0
    rejected: list[int] = []
    for lineno, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line:
            blank += 1
        elif len(line) > MAX_CHARS:
            rejected.append(lineno)
        else:
            valid.append(line)
    return valid, blank, rejected


def _upload_to_queue(file_path, queue, voice, model, fmt, speed, instructions):
    """Append one queue item per valid line of an uploaded .txt file (US1).

    Inherits the current form's voice/model/format/speed/instructions; appends to
    the existing queue (never clears it); reports an added/skipped/rejected summary.
    """
    queue = list(queue or [])
    if not file_path:
        return queue, _queue_view(queue), "Select a .txt file to load."
    try:
        valid, blank, rejected = _parse_upload(file_path)
    except UnicodeDecodeError:
        return queue, _queue_view(queue), "❌ File must be UTF-8 plain text."
    except OSError as exc:  # never leak a traceback to the user
        return queue, _queue_view(queue), f"❌ Could not read the file ({type(exc).__name__})."

    for line in valid:
        queue.append(
            {
                "text": line, "voice": voice, "model": model, "format": fmt,
                "speed": float(speed), "instructions": instructions, "tags": _empty_tags(),
            }
        )

    parts = [f"Added {len(valid)}"]
    if blank:
        parts.append(f"skipped {blank} blank")
    if rejected:
        shown = ", ".join(str(n) for n in rejected[:10]) + ("…" if len(rejected) > 10 else "")
        plural = "s" if len(rejected) != 1 else ""
        parts.append(f"rejected {len(rejected)} too long (line{plural} {shown})")
    status = " — ".join(parts) + f". Queue now has {len(queue)} item(s)."
    return queue, _queue_view(queue), status


def _remove_selected(queue, selected_index):
    queue = list(queue or [])
    if selected_index is not None and 0 <= selected_index < len(queue):
        queue.pop(selected_index)
    # Clear the selection so a second click can't pop a now-shifted index.
    return queue, _queue_view(queue), f"{len(queue)} item(s) in queue.", None


def _on_queue_select(queue, evt: gr.SelectData):
    """Row select → (index, edit-panel field values…, notice) to populate the editor."""
    idx = evt.index[0]
    queue = queue or []
    if not (0 <= idx < len(queue)):
        return (None, *(gr.update() for _ in range(21)), "No item selected.")
    item = queue[idx]
    return (
        idx,
        item["text"], item["voice"], item["model"], item["format"],
        item.get("instructions", ""),
        *_tags_to_fields(item.get("tags")),
        f"Editing item #{idx + 1} — change fields and click “Update item”.",
    )


def _update_queue_item(queue, idx, e_text, e_voice, e_model, e_fmt, e_instructions,
                       e_title, e_artist, e_album, e_genre, e_date, e_track,
                       e_languages, e_comment,
                       ct1_desc, ct1_val, ct2_desc, ct2_val,
                       cu1_desc, cu1_val, cu2_desc, cu2_val):
    """Write edited fields back into the selected queue item (US3); speed is untouched."""
    queue = list(queue or [])
    if idx is None or not (0 <= idx < len(queue)):
        return queue, _queue_view(queue), "Select a queue row to edit first."
    text = (e_text or "").strip()
    if not text:
        return queue, _queue_view(queue), "❌ Item text is required — previous value kept."
    if len(text) > MAX_CHARS:
        return queue, _queue_view(queue), (
            f"❌ Item exceeds {MAX_CHARS} characters — previous value kept.")
    tags = _collect_tags(e_title, e_artist, e_album, e_genre, e_date, e_track,
                         e_languages, e_comment,
                         ct1_desc, ct1_val, ct2_desc, ct2_val,
                         cu1_desc, cu1_val, cu2_desc, cu2_val)
    queue[idx] = {
        **queue[idx],                    # preserve speed (FR-014) and any other keys
        "text": text, "voice": e_voice, "model": e_model, "format": e_fmt,
        "instructions": e_instructions,  # kept even when model isn't gpt-4o-mini-tts (FR-012)
        "tags": tags,
    }
    note = f"✅ Updated item #{idx + 1}."
    has_tags = any((
        tags["title"], tags["artist"], tags["album"], tags["genre"], tags["comment"],
        tags["date"], tags["track"], tags["languages"], tags["custom_text"], tags["custom_url"],
    ))
    if has_tags and e_fmt in NO_TAGS:
        note += f" Tags will be skipped for {e_fmt}."
    elif tags["custom_url"] and e_fmt in ("flac", "opus"):
        note += f" Custom URL won't embed for {e_fmt}."
    return queue, _queue_view(queue), note


def _generate_all(queue, progress=gr.Progress()):
    queue = list(queue or [])
    if not queue:
        return None, "❌ Queue is empty."

    storage = get_storage()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    count, errors = 0, []
    with zipfile.ZipFile(tmp.name, "w") as zf:
        for item in progress.tqdm(queue, desc="Generating"):
            try:
                audio = generate_speech(
                    item["text"], item["model"], item["voice"],
                    item["format"], item["speed"], item.get("instructions"),
                )
                item_tags = item.get("tags") or _empty_tags()
                audio, _note, tagged = _apply_tags(audio, item["format"], item_tags)
                stem = slugify(item_tags.get("title", "")) or uuid.uuid4().hex
                path = storage.save(audio, f"{stem}.{item['format']}")
                record = {
                    "text_input": item["text"], "voice": item["voice"],
                    "model": item["model"], "format": item["format"],
                    "speed": item["speed"], "file_path": path, "file_size": len(audio),
                }
                record.update(_tag_record_fields(item_tags, tagged))
                insert_generation(record)
                zf.writestr(os.path.basename(path), audio)  # bytes in-hand; no disk re-read, backend-agnostic
            except TTSError as exc:
                errors.append(str(exc))
                continue
            except Exception as exc:  # never leak a traceback
                errors.append(type(exc).__name__)
                continue
            count += 1

    status = f"✅ Generated {count}/{len(queue)} item(s)."
    if errors:
        status += f" {len(errors)} failed: " + "; ".join(errors[:3])
    return (tmp.name if count else None), status


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #
def _char_count(text):
    return f"{len(text or '')} / {MAX_CHARS}"


def _toggle_instructions(model):
    return gr.update(visible=(model == "gpt-4o-mini-tts"))


def build_generate_tab():
    """Build the Generate tab; return the list of generation click events.

    The returned events let app.py chain a Library refresh after each generation.
    """
    with gr.Tab("Generate"):
        with gr.Row():
            with gr.Column():
                text = gr.Textbox(
                    label="Text", lines=5, max_lines=20, max_length=MAX_CHARS,
                    placeholder="Enter text to convert…",
                )
                counter = gr.Markdown(f"0 / {MAX_CHARS}")
                with gr.Row():
                    voice = gr.Dropdown(label="Voice", choices=VOICE_CHOICES, value="alloy")
                    model = gr.Dropdown(label="Model", choices=MODEL_CHOICES, value="tts-1")
                with gr.Row():
                    fmt = gr.Dropdown(
                        label="Format", choices=FORMAT_CHOICES, value="mp3",
                        info=("MP3/WAV use ID3v2.4.0 tags; FLAC/Opus use Vorbis/Opus tags. "
                              "PCM has no inline preview; PCM & AAC can't carry tags."),
                    )
                    speed = gr.Slider(
                        label="Speed", minimum=0.25, maximum=4.0, step=0.05, value=1.0
                    )
                instructions = gr.Textbox(
                    label="Voice instructions (gpt-4o-mini-tts only)", lines=2, visible=False
                )
                with gr.Accordion("Audio tags (optional)", open=False):
                    gr.Markdown("Embedded when the format supports it. MP3/WAV use "
                                "ID3v2.4.0; FLAC/Opus use Vorbis (custom URL skipped); "
                                "PCM and AAC can't carry tags — skipped with a note.")
                    with gr.Row():
                        t_title = gr.Textbox(label="Title", max_lines=1)
                        t_artist = gr.Textbox(label="Artist", max_lines=1)
                    with gr.Row():
                        t_album = gr.Textbox(label="Album", max_lines=1)
                        t_genre = gr.Textbox(label="Genre", max_lines=1)
                    with gr.Row():
                        t_date = gr.Textbox(label="Recording date (YYYY or YYYY-MM-DD)", max_lines=1)
                        t_track = gr.Textbox(label="Track (n or n/total)", max_lines=1)
                    with gr.Row():
                        t_languages = gr.Textbox(
                            label="Language(s) — ISO 639-2, comma-separated", max_lines=1)
                        t_comment = gr.Textbox(label="Comment", max_lines=1)
                    with gr.Accordion("Custom fields (optional)", open=False):
                        with gr.Row():
                            ct1_desc = gr.Textbox(label="Custom text 1 — name", max_lines=1)
                            ct1_val = gr.Textbox(label="Custom text 1 — value", max_lines=1)
                        with gr.Row():
                            ct2_desc = gr.Textbox(label="Custom text 2 — name", max_lines=1)
                            ct2_val = gr.Textbox(label="Custom text 2 — value", max_lines=1)
                        with gr.Row():
                            cu1_desc = gr.Textbox(label="Custom URL 1 — name", max_lines=1)
                            cu1_val = gr.Textbox(label="Custom URL 1 — URL", max_lines=1)
                        with gr.Row():
                            cu2_desc = gr.Textbox(label="Custom URL 2 — name", max_lines=1)
                            cu2_val = gr.Textbox(label="Custom URL 2 — URL", max_lines=1)
                generate_btn = gr.Button("Generate", variant="primary")
            with gr.Column():
                audio_out = gr.Audio(label="Preview", type="filepath")
                file_out = gr.File(label="Download")
                status = gr.Textbox(label="Status", interactive=False)

        text.change(_char_count, inputs=text, outputs=counter)
        model.change(_toggle_instructions, inputs=model, outputs=instructions)
        gen_event = generate_btn.click(
            _on_generate,
            inputs=[text, voice, model, fmt, speed, instructions,
                    t_title, t_artist, t_album, t_genre, t_date, t_track,
                    t_languages, t_comment,
                    ct1_desc, ct1_val, ct2_desc, ct2_val,
                    cu1_desc, cu1_val, cu2_desc, cu2_val],
            outputs=[audio_out, file_out, status],
        )

        # ----- Batch -----
        with gr.Accordion("Batch queue", open=False):
            queue_state = gr.State([])
            selected_index = gr.State(None)
            queue_df = gr.Dataframe(
                headers=QUEUE_HEADERS, interactive=False, label="Queue", wrap=True,
            )
            upload_file = gr.File(
                label="Upload .txt — one queue item per line (UTF-8)",
                file_types=[".txt"], file_count="single", type="filepath",
            )
            with gr.Row():
                add_btn = gr.Button("Add current form to queue")
                remove_btn = gr.Button("Remove selected")
                generate_all_btn = gr.Button("Generate all", variant="primary")
            batch_status = gr.Textbox(label="Batch status", interactive=False)
            zip_out = gr.File(label="Download all (zip)")

            with gr.Accordion("Edit selected item", open=False):
                edit_notice = gr.Markdown("Select a queue row to edit it. (Speed isn't editable here.)")
                e_text = gr.Textbox(label="Text", lines=3, max_length=MAX_CHARS)
                with gr.Row():
                    e_voice = gr.Dropdown(label="Voice", choices=VOICE_CHOICES)
                    e_model = gr.Dropdown(label="Model", choices=MODEL_CHOICES)
                with gr.Row():
                    e_fmt = gr.Dropdown(label="Format", choices=FORMAT_CHOICES)
                    e_instructions = gr.Textbox(
                        label="Voice instructions (gpt-4o-mini-tts only)", max_lines=2)
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
                    e_languages = gr.Textbox(
                        label="Language(s) — ISO 639-2, comma-separated", max_lines=1)
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
                update_btn = gr.Button("Update item", variant="primary")

        add_btn.click(
            _add_to_queue,
            inputs=[queue_state, text, voice, model, fmt, speed, instructions,
                    t_title, t_artist, t_album, t_genre, t_date, t_track,
                    t_languages, t_comment,
                    ct1_desc, ct1_val, ct2_desc, ct2_val,
                    cu1_desc, cu1_val, cu2_desc, cu2_val],
            outputs=[queue_state, queue_df, batch_status],
        )
        upload_file.upload(
            _upload_to_queue,
            inputs=[upload_file, queue_state, voice, model, fmt, speed, instructions],
            outputs=[queue_state, queue_df, batch_status],
        )
        queue_df.select(
            _on_queue_select,
            inputs=[queue_state],
            outputs=[selected_index, e_text, e_voice, e_model, e_fmt, e_instructions,
                     e_title, e_artist, e_album, e_genre, e_date, e_track,
                     e_languages, e_comment,
                     e_ct1_desc, e_ct1_val, e_ct2_desc, e_ct2_val,
                     e_cu1_desc, e_cu1_val, e_cu2_desc, e_cu2_val, edit_notice],
        )
        update_btn.click(
            _update_queue_item,
            inputs=[queue_state, selected_index, e_text, e_voice, e_model, e_fmt, e_instructions,
                    e_title, e_artist, e_album, e_genre, e_date, e_track,
                    e_languages, e_comment,
                    e_ct1_desc, e_ct1_val, e_ct2_desc, e_ct2_val,
                    e_cu1_desc, e_cu1_val, e_cu2_desc, e_cu2_val],
            outputs=[queue_state, queue_df, batch_status],
        )
        remove_btn.click(
            _remove_selected,
            inputs=[queue_state, selected_index],
            outputs=[queue_state, queue_df, batch_status, selected_index],
        )
        batch_event = generate_all_btn.click(
            _generate_all, inputs=[queue_state], outputs=[zip_out, batch_status]
        )

    return [gen_event, batch_event]
