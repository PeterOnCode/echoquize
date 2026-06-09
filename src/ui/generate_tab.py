"""Generate tab: single + batch text-to-speech generation. See contracts/ui-contract.md."""

import os
import tempfile
import uuid
import zipfile

import gradio as gr

from src.db.database import insert_generation
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
def _collect_tags(title, artist, album, comment, genre, year):
    raw = {
        "title": title, "artist": artist, "album": album,
        "comment": comment, "genre": genre, "year": year,
    }
    return {k: ((v or "").strip() or None) for k, v in raw.items()}


def _apply_tags(audio, fmt, tags):
    """Tag the raw audio *bytes* (via a temp file) before they reach storage.

    Returns ``(audio_bytes, status_note, written)``. Tagging bytes — not the stored
    path — keeps this correct for remote backends and keeps file_size in sync with
    the bytes actually saved. Never raises: a tag failure leaves the audio untagged
    rather than losing the generation (Principle VII).
    """
    if not any((v or "").strip() for v in tags.values()):
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
            return fh.read(), " Tags written.", True
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


def _on_generate(text, voice, model, fmt, speed, instructions,
                 t_title, t_artist, t_album, t_comment, t_genre, t_year):
    """Validate, synthesize, save, tag, persist; return (preview, download, status)."""
    text = (text or "").strip()
    if not text:
        return None, None, "❌ Text is required."
    if len(text) > MAX_CHARS:
        return None, None, f"❌ Text exceeds {MAX_CHARS} characters (got {len(text)})."

    tags = _collect_tags(t_title, t_artist, t_album, t_comment, t_genre, t_year)
    try:
        storage = get_storage()
        audio = generate_speech(text, model, voice, fmt, float(speed), instructions)
        audio, tag_note, tagged = _apply_tags(audio, fmt, tags)  # tag bytes before saving
        path = storage.save(audio, f"{uuid.uuid4()}.{fmt}")
        gid = insert_generation(
            {
                "text_input": text, "voice": voice, "model": model, "format": fmt,
                "speed": float(speed), "file_path": path, "file_size": len(audio),
                # persist tags only when they were actually embedded (no phantom metadata)
                "tag_title": tags["title"] if tagged else None,
                "tag_artist": tags["artist"] if tagged else None,
                "tag_album": tags["album"] if tagged else None,
                "tag_comment": tags["comment"] if tagged else None,
                "tag_genre": tags["genre"] if tagged else None,
                "tag_year": tags["year"] if tagged else None,
            }
        )
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


def _add_to_queue(queue, text, voice, model, fmt, speed, instructions):
    queue = list(queue or [])
    text = (text or "").strip()
    if not text:
        return queue, _queue_view(queue), "❌ Enter text before adding to the queue."
    if len(text) > MAX_CHARS:
        return queue, _queue_view(queue), f"❌ Item exceeds {MAX_CHARS} characters."
    queue.append(
        {
            "text": text, "voice": voice, "model": model, "format": fmt,
            "speed": float(speed), "instructions": instructions,
        }
    )
    return queue, _queue_view(queue), f"Queued — {len(queue)} item(s)."


def _remove_selected(queue, selected_index):
    queue = list(queue or [])
    if selected_index is not None and 0 <= selected_index < len(queue):
        queue.pop(selected_index)
    # Clear the selection so a second click can't pop a now-shifted index.
    return queue, _queue_view(queue), f"{len(queue)} item(s) in queue.", None


def _on_queue_select(evt: gr.SelectData):
    return evt.index[0]


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
                path = storage.save(audio, f"{uuid.uuid4()}.{item['format']}")
                insert_generation(
                    {
                        "text_input": item["text"], "voice": item["voice"],
                        "model": item["model"], "format": item["format"],
                        "speed": item["speed"], "file_path": path, "file_size": len(audio),
                    }
                )
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
                    fmt = gr.Dropdown(label="Format", choices=FORMAT_CHOICES, value="mp3")
                    speed = gr.Slider(
                        label="Speed", minimum=0.25, maximum=4.0, step=0.05, value=1.0
                    )
                instructions = gr.Textbox(
                    label="Voice instructions (gpt-4o-mini-tts only)", lines=2, visible=False
                )
                with gr.Accordion("Audio tags (optional)", open=False):
                    gr.Markdown("Embedded into the file when the format supports it. "
                                "PCM and AAC can't carry tags — they're skipped with a note.")
                    with gr.Row():
                        t_title = gr.Textbox(label="Title", max_lines=1)
                        t_artist = gr.Textbox(label="Artist", max_lines=1)
                    with gr.Row():
                        t_album = gr.Textbox(label="Album", max_lines=1)
                        t_genre = gr.Textbox(label="Genre", max_lines=1)
                    with gr.Row():
                        t_year = gr.Textbox(label="Year", max_lines=1)
                        t_comment = gr.Textbox(label="Comment", max_lines=1)
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
                    t_title, t_artist, t_album, t_comment, t_genre, t_year],
            outputs=[audio_out, file_out, status],
        )

        # ----- Batch -----
        with gr.Accordion("Batch queue", open=False):
            queue_state = gr.State([])
            selected_index = gr.State(None)
            queue_df = gr.Dataframe(
                headers=QUEUE_HEADERS, interactive=False, label="Queue", wrap=True,
            )
            with gr.Row():
                add_btn = gr.Button("Add current form to queue")
                remove_btn = gr.Button("Remove selected")
                generate_all_btn = gr.Button("Generate all", variant="primary")
            batch_status = gr.Textbox(label="Batch status", interactive=False)
            zip_out = gr.File(label="Download all (zip)")

        add_btn.click(
            _add_to_queue,
            inputs=[queue_state, text, voice, model, fmt, speed, instructions],
            outputs=[queue_state, queue_df, batch_status],
        )
        queue_df.select(_on_queue_select, outputs=selected_index)
        remove_btn.click(
            _remove_selected,
            inputs=[queue_state, selected_index],
            outputs=[queue_state, queue_df, batch_status, selected_index],
        )
        batch_event = generate_all_btn.click(
            _generate_all, inputs=[queue_state], outputs=[zip_out, batch_status]
        )

    return [gen_event, batch_event]
