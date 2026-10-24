import json
import logging
from collections.abc import AsyncIterator

from google.genai import types

from app.chat.speaker import LineSpeaker
from app.core.config import Settings
from app.guardrails.output import guard_reply
from app.llm.client import ChatTurn, LLMClient, to_contents
from app.llm.prompts import location_section, reply_system
from app.location.assistant import (
    TOOLS,
    LocationAssistant,
    PendingRide,
    is_confirmation,
)
from app.persona.models import Persona, ReplyExample
from app.persona.shortforms import expand_shortforms
from app.speech.cues import emojis_to_cues
from app.speech.tts import TTSClient
from app.storage.personas import PersonaStore

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 3


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


async def _generate(
    persona: Persona,
    turns: list[ChatTurn],
    examples: list[ReplyExample],
    llm: LLMClient,
    settings: Settings,
    location: LocationAssistant | None,
    pending_ride: PendingRide | None = None,
) -> AsyncIterator[tuple[str, object]]:
    """One model attempt: ("text", chunk) items, plus ("event", (name, data)) for UI cards
    produced by location tools. Tool results go back to the model, which then answers."""
    system = reply_system(persona, examples)
    history = turns[-settings.chat_max_history :]
    common = {
        "model": settings.llm_chat_model,
        "temperature": settings.llm_chat_temperature,
        "thinking": settings.llm_chat_thinking,
    }
    if location is None:
        async for chunk in llm.stream(system=system, turns=history, **common):
            yield "text", chunk
        return

    confirmed_result = None
    if pending_ride and is_confirmation(turns[-1].text):
        # A plain "yes" to a draft confirms it here, not via the model: booking must not
        # depend on the model remembering to call the tool.
        outcome = await location.plan_ride(
            pending_ride.origin_ref, pending_ride.destination_ref, confirmed=True
        )
        confirmed_result = outcome.result
        for event in outcome.events:
            yield "event", event
    system += location_section(location.saved_labels(), pending_ride, confirmed_result)
    common["model"] = settings.llm_tools_model
    contents = to_contents(history)
    for _round in range(MAX_TOOL_ROUNDS):
        calls: list[types.Part] = []
        said: list[str] = []
        async for kind, value in llm.stream_turn(
            system=system, contents=contents, tools=TOOLS, **common
        ):
            if kind == "text":
                said.append(value)
                yield "text", value
            else:
                calls.append(value)
        if not calls:
            return
        if said:
            yield (
                "text",
                "\n",
            )  # text before a tool call ("ruk dekhta hu") is its own bubble
        model_parts = (
            [types.Part.from_text(text="".join(said))] if said else []
        ) + calls
        contents.append(types.Content(role="model", parts=model_parts))
        responses = []
        for part in calls:
            call = part.function_call
            outcome = await location.execute(call.name, dict(call.args or {}))
            for event in outcome.events:
                yield "event", event
            responses.append(
                types.Part.from_function_response(
                    name=call.name, response=outcome.result
                )
            )
        contents.append(types.Content(role="user", parts=responses))


async def stream_reply(
    persona: Persona,
    turns: list[ChatTurn],
    llm: LLMClient,
    store: PersonaStore,
    settings: Settings,
    tts: TTSClient | None = None,
    location: LocationAssistant | None = None,
    pending_ride: PendingRide | None = None,
) -> AsyncIterator[str]:
    """SSE events: `delta` {text} while streaming, then `done` {bubbles, tts_text}, or `error`.
    `done` carries the output-guarded text, which the client shows in place of the deltas.
    With `tts`, each finished line is spoken right away: `audio` {index, format, audio}
    (base64) or `audio_error` {index, message} events arrive in line order, during and
    after the text. With `location`, the model may call location tools; their UI cards
    arrive as `ride_preview` {draft card}, `location` {confirmed ride card}, `choices`
    {options} and `saved_place` events."""
    stripper = PrefixStripper(persona.name)

    def speech_text(text: str) -> str:
        if persona.expand_shortforms_in_speech:
            return expand_shortforms(text, persona.shortforms)
        return text

    speaker = (
        LineSpeaker(
            tts,
            voice_id=persona.voice_id or settings.fish_default_voice_id,
            emoji_map=persona.emoji_map,
            prepare=speech_text,
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
            sent_cards = False
            for _attempt in range(2):
                async for kind, value in _generate(
                    persona, turns, examples, llm, settings, location, pending_ride
                ):
                    if kind == "event":
                        sent_cards = True
                        yield sse(*value)
                    elif text := stripper.feed(value):
                        for event in emit(text):
                            yield event
                if full or stripper.pending or sent_cards:
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
        spoken = "\n".join(speech_text(b) for b in bubbles)
        if persona.expand_shortforms_in_text:
            bubbles = [expand_shortforms(b, persona.shortforms) for b in bubbles]
        yield sse(
            "done",
            {
                "bubbles": bubbles,
                "tts_text": emojis_to_cues(spoken, persona.emoji_map),
            },
        )
        if speaker:
            async for name, data in speaker.drain():
                yield sse(name, data)
    finally:
        # No-op when everything was sent; stops paying for TTS if the client went away.
        if speaker:
            speaker.cancel()
