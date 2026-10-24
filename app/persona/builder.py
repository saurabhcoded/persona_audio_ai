"""Persona build (agents/workflows/persona-build.md). Input is sanitized messages only."""

import asyncio
import json
import logging
import re
from collections import defaultdict

import emoji
import numpy as np
from fastapi import HTTPException

from app.core.config import Settings
from app.ingest.models import Message
from app.llm import prompts
from app.llm.client import LLMClient
from app.persona.models import Persona, ReplyExample
from app.persona.pairs import build_pairs, to_bursts
from app.persona.shortforms import detect_shortforms
from app.persona.stats import compute_stats, describe
from app.speech.cues import EmojiCue
from app.storage.personas import PersonaStore

logger = logging.getLogger(__name__)

CARD_SAMPLE_MESSAGES = 400
CARD_SAMPLE_PAIRS = 40
EMOJI_MIN_USES = 3
EMOJI_MAX = 15
EMOJI_CONTEXTS = 8
_VALID_CUE = re.compile(r"^\[[^\[\]]{1,38}\](?:\[[^\[\]]{1,38}\])?$")


def _spread(items: list, n: int) -> list:
    """n items evenly spaced across the list (keeps early and late chat history)."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


async def _persona_card(
    llm: LLMClient, settings: Settings, name: str, sender: str, messages, pairs
) -> str:
    lines = [m.text.replace("\n", " ") for m in messages if m.sender == sender]
    exchanges = "\n\n".join(
        f"Them: {p.context}\n{name}: {p.reply}"
        for p in _spread(pairs, CARD_SAMPLE_PAIRS)
    )
    prompt = prompts.CARD_PROMPT.format(
        name=name,
        messages="\n".join(_spread(lines, CARD_SAMPLE_MESSAGES)),
        exchanges=exchanges,
    )
    card = await llm.generate(
        model=settings.llm_build_model, system=prompts.CARD_SYSTEM, prompt=prompt
    )
    return card.strip()


async def _emoji_map(
    llm: LLMClient, settings: Settings, name: str, sender: str, messages: list[Message]
) -> dict[str, EmojiCue]:
    contexts: dict[str, list[str]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    prev = ""
    for m in messages:
        if m.sender != sender:
            prev = m.text
            continue
        for e in {x["emoji"] for x in emoji.emoji_list(m.text)}:
            counts[e] += 1
            if len(contexts[e]) < EMOJI_CONTEXTS:
                contexts[e].append(f"Them: {prev[:150]}\n{name}: {m.text[:200]}")
    chosen = [
        e for e, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= EMOJI_MIN_USES
    ][:EMOJI_MAX]
    if not chosen:
        return {}
    blocks = "\n\n".join(
        f"### {e} (used {counts[e]} times)\n" + "\n---\n".join(contexts[e])
        for e in chosen
    )
    raw = await llm.generate(
        model=settings.llm_build_model,
        system=prompts.EMOJI_SYSTEM,
        prompt=prompts.EMOJI_PROMPT.format(name=name, blocks=blocks),
        json_schema=prompts.EMOJI_SCHEMA,
    )
    result = {}
    for item in json.loads(raw).get("items", []):
        cue = item.get("cue", "").strip()
        if item.get("emoji") in counts and _VALID_CUE.match(cue):
            result[item["emoji"]] = EmojiCue(
                cue=cue, spoken_as=item.get("spoken_as", "").strip()
            )
    return result


async def _embed_pairs(
    llm: LLMClient, settings: Settings, pairs: list[ReplyExample]
) -> np.ndarray:
    if not pairs:
        return np.zeros((0, settings.embedding_dim), dtype=np.float32)
    vectors = await llm.embed(
        [p.context for p in pairs],
        model=settings.embedding_model,
        dim=settings.embedding_dim,
        concurrency=settings.embedding_concurrency,
    )
    return np.asarray(vectors, dtype=np.float32)


async def build_persona(
    persona: Persona,
    messages: list[Message],
    store: PersonaStore,
    llm: LLMClient,
    settings: Settings,
) -> None:
    """Runs as a background task after POST /personas; persona.status goes building -> ready|failed."""
    sender = persona.sender_name or persona.name
    try:
        bursts = to_bursts(messages)
        stats = compute_stats(messages, sender, sum(b.sender == sender for b in bursts))
        pairs = build_pairs(bursts, sender)[-settings.persona_max_pairs :]
        store.save_messages(persona.id, messages)

        card, emoji_map, vectors, shortforms = await asyncio.gather(
            _persona_card(llm, settings, persona.name, sender, messages, pairs),
            _emoji_map(llm, settings, persona.name, sender, messages),
            _embed_pairs(llm, settings, pairs),
            detect_shortforms(llm, settings, persona.name, sender, messages),
        )
        store.save_index(persona.id, pairs, vectors)
        persona = persona.model_copy(
            update={
                "status": "ready",
                "card": card,
                "style": describe(stats),
                "stats": stats.model_dump(),
                "emoji_map": emoji_map,
                "shortforms": shortforms,
                "tagline": f"From chat · {stats.messages} messages · {len(pairs)} reply examples",
            }
        )
    except Exception:
        # Never log message text (agents/steering.md rule 3).
        logger.exception("Persona build failed for persona=%s", persona.id)
        persona = persona.model_copy(
            update={
                "status": "failed",
                "error": "Build failed. Check the server log and try again.",
            }
        )
    try:
        current = store.get(persona.id)
    except HTTPException:
        return  # deleted while building: don't bring it back
    # Keep a voice the user picked while the build was running.
    store.save(persona.model_copy(update={"voice_id": current.voice_id}))
