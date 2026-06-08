"""Echoquize — Gradio entry point. See contracts/ui-contract.md."""

import gradio as gr

import config
from src.db.database import init_db
from src.ui.generate_tab import build_generate_tab
from src.ui.library_tab import build_library_tab


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Echoquize") as demo:
        gr.Markdown("# 🔊 Echoquize — Text-to-Speech Studio")
        with gr.Tabs():
            gen_events = build_generate_tab()
            lib = build_library_tab()

        # Refresh the Library after each (single or batch) generation, and on load.
        for event in gen_events:
            event.then(lib["reload"], inputs=lib["inputs"], outputs=lib["outputs"])
        demo.load(lib["reload"], inputs=lib["inputs"], outputs=lib["outputs"])
    return demo


def main() -> None:
    init_db()
    demo = build_app()
    demo.launch(server_name=config.HOST, server_port=config.PORT, share=False)


if __name__ == "__main__":
    main()
