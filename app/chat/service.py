import json
import logging
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.guardrails.output import guard_reply
from app.llm.client import ChatTurn, LLMClient
from app.llm.prompts import reply_system
from app.persona.models import Persona, ReplyExample
from app.speech.cues import emojis_to_cues
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
) -> AsyncIterator[str]:
    """SSE events: `delta` {text} while streaming, then `done` {bubbles, tts_text}, or `error`.
    `done` carries the output-guarded text, which the client shows in place of the deltas."""
    stripper = PrefixStripper(persona.name)
    full = []
    try:
        examples = await _examples(persona, turns, llm, store, settings)
        async for chunk in llm.stream(
            model=settings.llm_chat_model,
            system=reply_system(persona, examples),
            turns=turns[-settings.chat_max_history :],
            temperature=settings.llm_chat_temperature,
            thinking=settings.llm_chat_thinking,
        ):
            if text := stripper.feed(chunk):
                full.append(text)
                yield sse("delta", {"text": text})
        if text := stripper.flush():
            full.append(text)
            yield sse("delta", {"text": text})
    except Exception:
        # Never log message text (agents/steering.md rule 3).
        logger.exception("Reply stream failed for persona=%s", persona.id)
        yield sse("error", {"message": "The model failed to reply. Try again."})
        return

    reply = guard_reply("".join(full))
    bubbles = [line.strip() for line in reply.splitlines() if line.strip()]
    yield sse(
        "done",
        {
            "bubbles": bubbles,
            "tts_text": emojis_to_cues("\n".join(bubbles), persona.emoji_map),
        },
    )
