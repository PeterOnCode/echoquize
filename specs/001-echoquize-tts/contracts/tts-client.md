# Contract: src/tts/client.py

Wraps the OpenAI TTS API and returns raw audio bytes. (Principles VII, III.)

## Signature

```python
def generate_speech(
    text: str,
    model: str,
    voice: str,
    format: str,
    speed: float,
    instructions: str | None = None,
) -> bytes: ...
```

## Inputs & domains

| Param | Domain |
|-------|--------|
| `text` | non-empty, ≤ 4096 chars (validated before the API call) |
| `model` | `tts-1` \| `tts-1-hd` \| `gpt-4o-mini-tts` |
| `voice` | `alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar` |
| `format` | `mp3 \| opus \| aac \| flac \| wav \| pcm` |
| `speed` | 0.25–4.0 |
| `instructions` | only forwarded when `model == gpt-4o-mini-tts`; otherwise omitted |

## Behavior

- Uses `client.audio.speech.with_streaming_response.create(...)` + `response.read()` to obtain bytes.
- Client initialized with `OpenAI(api_key=config.OPENAI_API_KEY)`.
- Returns non-empty `bytes` on success.

## Errors (surfaced as friendly messages by the UI — Principle VII)

| Raised condition | Caller message |
|------------------|----------------|
| empty or > 4096 chars | "Text is required" / "Text exceeds 4096 characters" (no API call) |
| `openai.AuthenticationError` | "Invalid API key — check your .env" |
| `openai.RateLimitError` | "Rate limited — please retry shortly" |
| `openai.APIError` | "Speech service error — please try again" |

Error messages MUST NOT leak the API key or internal paths (readiness CHK023).

## Contract test (manual)

`generate_speech('hello', 'tts-1', 'alloy', 'mp3', 1.0)` → returns non-empty `bytes`.
