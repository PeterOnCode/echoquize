"""Generate tab: single text-to-speech generation. See contracts/ui-contract.md."""

import os
import uuid

import gradio as gr

from src.db.database import insert_generation
from src.storage import get_storage
from src.tts.client import MAX_CHARS, TTSError, generate_speech

VOICE_CHOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
]
MODEL_CHOICES = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]
FORMAT_CHOICES = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
NO_PREVIEW = {"pcm"}  # raw bytes — no inline player


def _on_generate(text, voice, model, fmt, speed, instructions):
    """Validate, synthesize, save, persist; return (preview, download, status)."""
    text = (text or "").strip()
    if not text:
        return None, None, "❌ Text is required."
    if len(text) > MAX_CHARS:
        return None, None, f"❌ Text exceeds {MAX_CHARS} characters (got {len(text)})."

    try:
        audio = generate_speech(text, model, voice, fmt, float(speed), instructions)
    except TTSError as exc:
        return None, None, f"❌ {exc}"
    except Exception as exc:  # safety net — never leak a traceback to the user
        return None, None, f"❌ Unexpected error ({type(exc).__name__})."

    filename = f"{uuid.uuid4()}.{fmt}"
    path = get_storage().save(audio, filename)
    gid = insert_generation(
        {
            "text_input": text,
            "voice": voice,
            "model": model,
            "format": fmt,
            "speed": float(speed),
            "file_path": path,
            "file_size": len(audio),
        }
    )

    status = (
        f"✅ Generated {len(audio) / 1024:.1f} KB — saved as "
        f"{os.path.basename(path)} (id {gid[:8]})."
    )
    if fmt in NO_PREVIEW:
        status += " Inline preview is unavailable for PCM — download only."
        return None, path, status
    return path, path, status


def _char_count(text):
    return f"{len(text or '')} / {MAX_CHARS}"


def _toggle_instructions(model):
    return gr.update(visible=(model == "gpt-4o-mini-tts"))


def build_generate_tab():
    """Build the Generate tab (call inside a gr.Tabs/gr.Blocks context)."""
    with gr.Tab("Generate"):
        with gr.Row():
            with gr.Column():
                text = gr.Textbox(
                    label="Text",
                    lines=5,
                    max_lines=20,
                    max_length=MAX_CHARS,
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
                    label="Voice instructions (gpt-4o-mini-tts only)",
                    lines=2,
                    visible=False,
                )
                generate_btn = gr.Button("Generate", variant="primary")
            with gr.Column():
                audio_out = gr.Audio(label="Preview", type="filepath")
                file_out = gr.File(label="Download")
                status = gr.Textbox(label="Status", interactive=False)

        text.change(_char_count, inputs=text, outputs=counter)
        model.change(_toggle_instructions, inputs=model, outputs=instructions)
        generate_btn.click(
            _on_generate,
            inputs=[text, voice, model, fmt, speed, instructions],
            outputs=[audio_out, file_out, status],
        )
