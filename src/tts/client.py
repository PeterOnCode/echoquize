"""OpenAI TTS client wrapper. See contracts/tts-client.md.

Returns raw audio bytes and maps OpenAI errors to friendly, user-facing
messages (Constitution Principle VII).
"""

import openai
from openai import OpenAI

import config

MODELS = ("tts-1", "tts-1-hd", "gpt-4o-mini-tts")
VOICES = (
    "alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova",
    "sage", "shimmer", "verse", "marin", "cedar",
)
FORMATS = ("mp3", "opus", "aac", "flac", "wav", "pcm")
MAX_CHARS = 4096

_client = OpenAI(api_key=config.OPENAI_API_KEY)


class TTSError(Exception):
    """User-facing TTS error carrying a friendly message."""


def generate_speech(
    text: str,
    model: str,
    voice: str,
    format: str,
    speed: float,
    instructions: str | None = None,
) -> bytes:
    """Synthesize ``text`` to audio bytes in ``format``.

    ``instructions`` is forwarded only for ``gpt-4o-mini-tts``.
    """
    text = (text or "").strip()
    if not text:
        raise TTSError("Text is required.")
    if len(text) > MAX_CHARS:
        raise TTSError(f"Text exceeds {MAX_CHARS} characters (got {len(text)}).")

    kwargs = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": format,
        "speed": speed,
    }
    if model == "gpt-4o-mini-tts" and instructions:
        kwargs["instructions"] = instructions

    try:
        with _client.audio.speech.with_streaming_response.create(**kwargs) as response:
            return response.read()
    except openai.AuthenticationError as exc:
        raise TTSError("Invalid API key — check your .env.") from exc
    except openai.RateLimitError as exc:
        raise TTSError("Rate limited — please retry shortly.") from exc
    except openai.APIError as exc:
        raise TTSError("Speech service error — please try again.") from exc
