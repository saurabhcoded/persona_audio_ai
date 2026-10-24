import json
import logging
from collections.abc import AsyncIterator

from app.chat.speaker import LineSpeaker
from app.core.config import Settings
from app.guardrails.output import guard_reply
from app.llm.client import ChatTurn, LLMClient
from app.llm.prompts import reply_system
from app.persona.models import Persona, ReplyExample
from app.speech.cues import emojis_to_cues
from app.speech.tts import TTSClient
from app.storage.personas import PersonaStore

logger = logging.getLogger(__name__)


class PrefixStripper:
    """Drops a leading "Name:" from each streamed line; models echo the few-shot labels."""

    def __init__(self, name: str):
        self.prefix = f"{name}:"
        self.pending = ""
        self.at_line_start = True

    def feed(self, chunk: str) -> str:
        out = []
        for ch in chunk:
            if not self.at_line_start:
                out.append(ch)
                self.at_line_start = ch == "\n"
                continue
            if ch == "\n":
                out.append(self.pending.strip() + "\n")
                self.pending = ""
                continue
            self.pending += ch
            head = self.pending.lstrip()
            if head == self.prefix:
                self.pending = ""
            elif not self.prefix.startswith(head):
                out.append(head)
                self.pending = ""
                self.at_line_start = False
        return "".join(out)

    def flush(self) -> str:
        rest, self.pending = self.pending.strip(), ""
        return rest


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _examples(
    persona: Persona,
    turns: list[ChatTurn],
    llm: LLMClient,
    store: PersonaStore,
    settings: Settings,
) -> list[ReplyExample]:
    """The persona's real replies to messages most similar to the user's last one."""
    index = store.load_index(persona.id)
    if index is None or not index.pairs:
        return persona.examples
    [query] = await llm.embed(
        [turns[-1].text], model=settings.embedding_model, dim=settings.embedding_dim
    )
    return index.search(query, settings.retrieval_pairs_k)


async def stream_reply(
    persona: Persona,
    turns: list[ChatTurn],
    llm: LLMClient,
    store: PersonaStore,
    settings: Settings,
    tts: TTSClient | None = None,
) -> AsyncIterator[str]:
    """SSE events: `delta` {text} while streaming, then `done` {bubbles, tts_text}, or `error`.
    `done` carries the output-guarded text, which the client shows in place of the deltas.
    With `tts`, each finished line is spoken right away: `audio` {index, format, audio}
    (base64) or `audio_error` {index, message} events arrive in line order, during and
    after the text."""
    stripper = PrefixStripper(persona.name)
    speaker = (
        LineSpeaker(
            tts,
            voice_id=persona.voice_id or settings.fish_default_voice_id,
            emoji_map=persona.emoji_map,
            audio_format=settings.fish_tts_format,
            concurrency=settings.tts_stream_concurrency,
        )
        if tts
        else None
    )
    full: list[str] = []

    def emit(text: str) -> list[str]:
        full.append(text)
        events = [sse("delta", {"text": text})]
        if speaker:
            speaker.feed(text)
            events += [sse(name, data) for name, data in speaker.ready()]
        return events

    try:
        try:
            examples = await _examples(persona, turns, llm, store, settings)
            # Gemini occasionally ends with no text (finish_reason MALFORMED_RESPONSE):
            # retry once, which is safe because nothing has been sent yet.
            for _attempt in range(2):
                async for chunk in llm.stream(
                    model=settings.llm_chat_model,
                    system=reply_system(persona, examples),
                    turns=turns[-settings.chat_max_history :],
                    temperature=settings.llm_chat_temperature,
                    thinking=settings.llm_chat_thinking,
                ):
                    if text := stripper.feed(chunk):
                        for event in emit(text):
                            yield event
                if full or stripper.pending:
                    break
                logger.warning(
                    "Empty reply from model for persona=%s; retrying", persona.id
                )
            if text := stripper.flush():
                for event in emit(text):
                    yield event
        except Exception:
            # Never log message text (agents/steering.md rule 3).
            logger.exception("Reply stream failed for persona=%s", persona.id)
            yield sse("error", {"message": "The model failed to reply. Try again."})
            return

        if speaker:
            speaker.finish()  # start the last line before sending `done`
        reply = guard_reply("".join(full))
        bubbles = [line.strip() for line in reply.splitlines() if line.strip()]
        yield sse(
            "done",
            {
                "bubbles": bubbles,
                "tts_text": emojis_to_cues("\n".join(bubbles), persona.emoji_map),
            },
        )
        if speaker:
            async for name, data in speaker.drain():
                yield sse(name, data)
    finally:
        # No-op when everything was sent; stops paying for TTS if the client went away.
        if speaker:
            speaker.cancel()
