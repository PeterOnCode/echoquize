"""Echoquize — Gradio entry point. See contracts/ui-contract.md."""

import gradio as gr

import config
from src.db.database import init_db
from src.ui.generate_tab import build_generate_tab
from src.ui.library_tab import build_library_tab
from src.version import app_version


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Echoquize") as demo:
        # Show the version next to the title when known; omit it otherwise so a
        # missing/garbled version never blocks startup (FR-025–FR-027, US8).
        title = "# 🔊 Echoquize — Text-to-Speech Studio"
        version = app_version()
        if version:
            title += (
                f' <small style="color: var(--body-text-color-subdued);'
                f' font-weight: normal;">v{version}</small>'
            )
        # Trusted, static content (version comes from our own pyproject) — render
        # the inline style verbatim instead of having it sanitized away.
        gr.Markdown(title, sanitize_html=False)
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
    # Optional single-owner login: only enforced when BOTH credentials are set
    # (unset → open access, per FR-017). HOST stays 0.0.0.0 for container reach.
    if config.UI_USERNAME and config.UI_PASSWORD:
        auth = (config.UI_USERNAME, config.UI_PASSWORD)
    else:
        auth = None
        if config.UI_USERNAME or config.UI_PASSWORD:
            # Partial config is almost always a mistake — surface it loudly so the
            # operator isn't surprised by an open instance (Principle VII).
            print(
                "⚠️  Only one of UI_USERNAME / UI_PASSWORD is set — authentication "
                "is DISABLED (open access). Set BOTH to require login.",
                flush=True,
            )
    demo.launch(
        server_name=config.HOST,
        server_port=config.PORT,
        share=False,
        auth=auth,
    )


if __name__ == "__main__":
    main()
